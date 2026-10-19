"""Deterministic synthetic labour-market universe for the pilot (4 states, 170 districts, 24 trades, 36 months).

A latent "true openings" process is generated first. Each simulated source then observes it with its own
coverage, noise, duplication and publication lag, as real portals, NCS, EPFO and e-Shram would. The
pipeline never reads the truth table; it exists only to validate the methods.
"""
from __future__ import annotations
import argparse
import numpy as np
from .. import catalog, official
from ..db import PERIODS, CURRENT_FY, COMPLETED_FYS, add_months, connect, fiscal_year, month_index

SEED = 2026
SYNTH_NOTE = "Synthetic demonstration data generated for SIH evaluation - not official government statistics."

SOURCES = [
    # key, name, type, access, grain, lag, side
    ("portal", "Online job portals (aggregated feed)", "job_portal", "Simulated portal API aggregate", "district x NCO x month", 0, "demand"),
    ("ncs", "National Career Service vacancies", "government_portal", "Simulated NCS vacancy extract", "district x NCO x month", 1, "demand"),
    ("epfo", "EPFO new payroll subscribers", "administrative", "Simulated EPFO payroll release", "district x sector x month", 2, "demand"),
    ("eshram", "e-Shram registered job-seekers", "administrative", "Simulated e-Shram extract", "district x NCO x month", 1, "supply"),
    ("postings", "Raw job postings sample (text)", "job_portal", "Simulated portal scrape (12 months)", "posting", 0, "demand"),
    ("sidh", "Skill India Digital Hub training records", "administrative", "Simulated SIDH cycle extract", "centre x QP x FY", 0, "supply"),
    ("benchmark", "Annual establishment hiring benchmark", "survey", "Simulated annual benchmark", "state x sector x FY", 6, "anchor"),
    ("invest", "Investment project pipeline", "industry", "Simulated Invest-India style tracker", "project", 0, "demand"),
]

PORTAL_ONLINE = {"IT": 1.35, "HC": 1.0, "EV": 1.0, "LG": 0.9, "RE": 0.7, "CN": 0.35}
FORMAL_SHARE = {"IT": 0.85, "HC": 0.55, "EV": 0.7, "RE": 0.6, "LG": 0.45, "CN": 0.15}
ESHRAM_RATIO = {"CN": 1.3, "LG": 0.9, "HC": 0.25, "EV": 0.2, "RE": 0.15, "IT": 0.1}
MIGRATION_SECTOR = {"CN": 1.0, "LG": 0.7, "HC": 0.45, "IT": 0.55, "EV": 0.5, "RE": 0.3}
STATE_HUB = {"Karnataka": "Bengaluru Urban", "Maharashtra": "Pune", "Odisha": "Khordha", "Uttar Pradesh": "Gautam Buddha Nagar"}
EMPLOYER_PREFIX = ["Shakti", "Sai", "Ganesh", "Vasudha", "Tejas", "Aarav", "Navya", "Sahyadri", "Kalinga", "Ganga", "Vindhya", "Kaveri", "Utkal", "Avadh", "Deccan", "Pragati", "Unnati", "Sarthi"]
EMPLOYER_SUFFIX = {"RE": ["Solar Pvt Ltd", "Renewables", "Green Energy LLP"], "EV": ["Motors", "E-Mobility Pvt Ltd", "Autotech"], "HC": ["Hospital", "Healthcare", "Diagnostics"],
                   "IT": ["Infotech", "Data Services", "Technologies"], "LG": ["Logistics", "Supply Chain Pvt Ltd", "Warehousing"], "CN": ["Constructions", "Infra Projects", "Builders"]}
PORTALS = ["JobPortal-A", "ClassifiedApp-B", "NCS", "GigPlatform-C"]


def month_matrix_investments(districts, trades, idx_of):
    """Latent hiring flow (openings per month) created by each investment project."""
    nd, nt, nm = len(districts), len(trades), len(PERIODS) + 24
    out = np.zeros((nd, nt, nm))
    tix = {t["code"]: i for i, t in enumerate(trades)}
    for name, district, sector, capex, jobs_ops, jobs_build, announced, build_start, ops_start, ramp in catalog.INVESTMENTS:
        d = idx_of[district]
        b0, o0 = month_index(build_start), month_index(ops_start)
        build_len = max(3, o0 - b0)
        for code, share in catalog.CONSTRUCTION_SHARES.items():
            for m in range(max(0, b0), min(nm, b0 + build_len)):
                out[d, tix[code], m] += jobs_build * share / build_len * 0.55   # build workforce churns ~55%/project
        for code, share in catalog.staffing_shares(sector).items():
            hire_start = o0 - 2                                                   # firms hire ahead of start of operations
            for m in range(max(0, hire_start), nm):
                k = m - hire_start
                out[d, tix[code], m] += jobs_ops * share * (1 / ramp if k < ramp else 0.015)
    return out


def anchor_to_official(level, districts, trades) -> dict | None:
    """Rescale each state so the simulated EPFO (formal-hiring) state shares equal the official EPFO net-payroll shares.

    The multiplier acts with strength = the sector's formal share, so formal trades follow official EPFO while
    largely informal trades (construction) keep their population-driven size. Iterated to convergence; only
    relative state sizes are anchored - absolute volumes stay synthetic because official EPFO covers all industries.
    """
    shares = official.state_shares("net_payroll_latest")
    if not shares:
        return None
    states = np.array([d["state"] for d in districts])
    formal = np.array([FORMAL_SHARE[t["sector"]] for t in trades])
    before = None
    for _ in range(25):
        formal_hires = {st: float((level[states == st] * formal[None, :]).sum()) for st in shares}
        total = sum(formal_hires.values())
        sim = {st: v / total for st, v in formal_hires.items()}
        before = before or sim
        for st in shares:
            level[states == st] *= (shares[st] / sim[st]) ** formal[None, :]
    return {"official_epfo_share": {k: round(v, 4) for k, v in shares.items()}, "simulated_share_before": {k: round(v, 4) for k, v in before.items()},
            "simulated_share_after": {k: round(v, 4) for k, v in sim.items()}}


def generate(c, rng):
    districts = catalog.load_districts()
    trades = catalog.trades()
    idx_of = {d["district"]: i for i, d in enumerate(districts)}
    for name in list(catalog.CLUSTERS) + [i[1] for i in catalog.INVESTMENTS] + list(catalog.MIGRANT_ORIGINS) + list(catalog.MIGRANT_DESTINATIONS) + list(catalog.HUBS):
        assert name in idx_of, f"unknown district in catalog: {name}"
    nd, nt, nm = len(districts), len(trades), len(PERIODS)
    months = np.array([int(p[5:]) for p in PERIODS])

    # ---------- latent truth ----------
    urban = np.array([d["urban"] for d in districts])
    popw = np.array([d["pop_weight"] for d in districts]) * np.exp(rng.normal(0, 0.18, nd))
    affinity = np.array([t["urban_affinity"] for t in trades])
    base = np.array([t["base"] for t in trades]) * 4.0
    growth = np.array([t["growth"] for t in trades])
    cluster = np.ones((nd, nt))
    for dname, mult in catalog.CLUSTERS.items():
        for j, t in enumerate(trades):
            cluster[idx_of[dname], j] = mult.get(t["sector"], 1.0)
    urban_factor = np.exp(np.outer(urban - 0.4, affinity) * 2.2)
    level = base[None, :] * popw[:, None] * urban_factor * cluster * np.exp(rng.normal(0, 0.12, (nd, nt)))
    anchor = anchor_to_official(level, districts, trades)
    g = growth[None, :] + rng.normal(0, 0.04, (nd, nt))
    season = np.array([catalog.SEASONS[t["season"]] for t in trades])[:, months - 1]  # (nt, nm)
    trend = (1 + g[:, :, None]) ** (np.arange(nm)[None, None, :] / 12)
    noise = np.exp(rng.normal(0, 0.07, (nd, nt, nm)))
    invest_full = month_matrix_investments(districts, trades, idx_of)
    invest = invest_full[:, :, :nm]
    truth = level[:, :, None] * season[None, :, :] * trend * noise + invest
    truth = np.maximum(truth, 0.3)

    # ---------- reference tables ----------
    c.executemany("INSERT INTO districts VALUES(?,?,?,?,?,?,?,?)", [(d["lgd"], d["state"], d["district"], d["lat"], d["lon"], d["urban"], round(float(popw[i]), 3), d["aspirational"]) for i, d in enumerate(districts)])
    V = catalog.VERIFICATION
    c.executemany("INSERT INTO trades VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [(t["code"], t["title"], t["sector"], catalog.SECTORS[t["sector"]], t["qp_code"], t["nsqf_level"], t["hours"], t["cost_per_seat"], t["women_share"], t["entry_wage"], t["emerging"],
                                                                                 V[t["code"]]["nco"], V[t["code"]]["nco_status"], V[t["code"]]["qp_status"], V[t["code"]]["qp_title"], V[t["code"]]["source"], V[t["code"]]["note"]) for t in trades])
    c.executemany("INSERT INTO qp_skills VALUES(?,?)", [(code, s) for code, (qp, _) in catalog.SKILLS.items() for s in qp])
    sid = {}
    for key, name, stype, access, grain, lag, side in SOURCES:
        sid[key] = c.execute("INSERT INTO sources(key,name,source_type,access_method,is_synthetic,grain,lag_months,side,reporting_note) VALUES(?,?,?,?,1,?,?,?,?)", (key, name, stype, access, grain, lag, side, SYNTH_NOTE)).lastrowid
    c.executemany("INSERT INTO investments(name,lgd,sector,capex_cr,jobs_ops,jobs_build,announced,build_start,ops_start,ramp_months) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  [(n, districts[idx_of[d]]["lgd"], s, cap, jo, jb, a, b, o, r) for n, d, s, cap, jo, jb, a, b, o, r in catalog.INVESTMENTS])
    c.executemany("INSERT INTO synthetic_truth VALUES(?,?,?,?)", [(PERIODS[m], districts[i]["lgd"], trades[j]["code"], round(float(truth[i, j, m]), 2)) for i in range(nd) for j in range(nt) for m in range(nm)])

    # ---------- demand-side sources ----------
    sector_of = np.array([t["sector"] for t in trades])
    online = np.array([PORTAL_ONLINE[s] for s in sector_of])
    dup = np.where(sector_of == "IT", 1.45, 1.28)
    cov_portal = np.clip((0.22 + 0.5 * urban)[:, None] * online[None, :], 0.03, 0.95)
    portal = rng.poisson(truth * (cov_portal * dup)[:, :, None])
    # Rural construction / RE postings are often absent from portals.
    missing_portal = (urban[:, None] < 0.3) & np.isin(sector_of, ["CN", "RE"])[None, :] & (rng.random((nd, nt)) < 0.45)
    sig = []
    for i in range(nd):
        for j in range(nt):
            if missing_portal[i, j]:
                continue
            for m in range(nm):
                sig.append((sid["portal"], PERIODS[m], districts[i]["lgd"], sector_of[j], trades[j]["code"], int(portal[i, j, m])))
    ncs_cov = np.where(sector_of == "HC", 0.2, 0.13)
    lagged = np.concatenate([truth[:, :, :1], truth[:, :, :-1]], axis=2)
    ncs = rng.poisson(lagged * ncs_cov[None, :, None])
    ncs_mask = rng.random((nd, nt, nm)) < 0.08
    for i in range(nd):
        for j in range(nt):
            for m in range(nm - 1):  # one-month publication lag: latest month not yet released
                if not ncs_mask[i, j, m]:
                    sig.append((sid["ncs"], PERIODS[m], districts[i]["lgd"], sector_of[j], trades[j]["code"], int(ncs[i, j, m])))
    for s in catalog.SECTORS:
        cols = np.where(sector_of == s)[0]
        payroll = rng.poisson(truth[:, cols, :].sum(axis=1) * FORMAL_SHARE[s] * 0.6)
        for i in range(nd):
            for m in range(nm - 2):  # two-month publication lag
                sig.append((sid["epfo"], PERIODS[m], districts[i]["lgd"], s, "", int(payroll[i, m])))
    # e-Shram: stock of registered informal workers seeking work in the trade (supply-side pool).
    origin_p = np.array([catalog.MIGRANT_ORIGINS.get(d["district"], 0.0) for d in districts])
    esh_ratio = np.array([ESHRAM_RATIO[s] for s in sector_of])
    annual = truth[:, :, :12].sum(axis=2)
    for m in range(nm - 1):
        stock = rng.poisson(annual * esh_ratio[None, :] * (1 + origin_p[:, None]) * (0.85 + 0.15 * m / nm) / 12)
        for i in range(nd):
            for j in range(nt):
                sig.append((sid["eshram"], PERIODS[m], districts[i]["lgd"], sector_of[j], trades[j]["code"], int(stock[i, j])))
    c.executemany("INSERT INTO signals VALUES(?,?,?,?,?,?)", sig)

    # Benchmarks: annual establishment hiring by state x sector for completed FYs.
    states = sorted({d["state"] for d in districts})
    st_idx = {s: [i for i, d in enumerate(districts) if d["state"] == s] for s in states}
    fy_of = [fiscal_year(p) for p in PERIODS]
    bench = []
    for fy in ["2024-25", "2025-26"]:
        mm = [m for m in range(nm) if fy_of[m] == fy]
        for s in states:
            for sec in catalog.SECTORS:
                cols = np.where(sector_of == sec)[0]
                v = truth[np.ix_(st_idx[s], cols, mm)].sum() * float(np.exp(rng.normal(0, 0.03)))
                bench.append((s, sec, fy, round(v)))
    c.executemany("INSERT INTO benchmarks VALUES(?,?,?,?)", bench)

    # ---------- supply side: centres and training cycles ----------
    schemes = ["PMKVY 4.0", "ITI", "JSS", "PMKK", "DDU-GKY", "State Skill Mission"]
    centres = []
    for i, d in enumerate(districts):
        n = 2 + int(round(popw[i] * 1.6)) + (1 if d["urban"] > 0.5 else 0)
        for k in range(n):
            lat = d["lat"] + rng.normal(0, 0.09)
            lon = d["lon"] + rng.normal(0, 0.09)
            cap = int(rng.integers(6, 26) * 50)
            centres.append([d["lgd"], f"{d['district']} {schemes[k % len(schemes)]} Centre {k + 1}", lat, lon, schemes[k % len(schemes)], cap])
    centre_ids = {}
    for row in centres:
        cid = c.execute("INSERT INTO centres(lgd,name,lat,lon,scheme,capacity) VALUES(?,?,?,?,?,?)", (row[0], row[1], round(row[2], 4), round(row[3], 4), row[4], row[5])).lastrowid
        centre_ids.setdefault(row[0], []).append(cid)
    supply_ratio = np.array([t["supply_ratio"] for t in trades])
    yield_rate = 0.85 * 0.86
    sup = []
    # Seat planning in reality lags demand: seats for FY k are sized on demand observed ~1 year earlier,
    # excluding new investment hiring that planners could not yet see.
    organic = truth - invest
    persistent = rng.normal(0, 0.3, (nd, nt))      # durable local over/under-provision (centre legacy, state priorities)
    for fy_i, fy in enumerate(COMPLETED_FYS + [CURRENT_FY]):
        ref = [m for m in range(nm) if fy_of[m] == (COMPLETED_FYS[max(0, fy_i - 1)])] or list(range(12))
        ref_demand = organic[:, :, ref].sum(axis=2) * 12 / len(ref)
        actual_mm = [m for m in range(nm) if fy_of[m] == fy]
        actual_demand = truth[:, :, actual_mm].sum(axis=2) * 12 / max(1, len(actual_mm)) if actual_mm else ref_demand
        for i, d in enumerate(districts):
            lgd = d["lgd"]
            for j, t in enumerate(trades):
                modifier = 1.0
                if t["sector"] in ("CN", "LG"):
                    modifier *= 1 + 2.2 * origin_p[i]   # origin districts over-train for migrant labour markets
                if d["state"] == "Odisha" and t["sector"] == "CN":
                    modifier *= 1.3
                seats = ref_demand[i, j] * supply_ratio[j] * 1.3 * modifier / yield_rate * float(np.exp(persistent[i, j] + rng.normal(0, 0.1)))
                if seats < 10:
                    continue
                seats = int(round(seats / 5) * 5)
                cids = centre_ids[lgd]
                split = [1.0] if seats < 120 or len(cids) == 1 else [0.6, 0.4]
                chosen = rng.choice(len(cids), size=len(split), replace=False)
                certified_total = seats * yield_rate
                balance = actual_demand[i, j] / max(1.0, certified_total / max(0.3, 1 - origin_p[i] * 0.5))
                for share, ck in zip(split, chosen):
                    s_seats = int(round(seats * share))
                    enrolled = int(s_seats * rng.uniform(0.86, 0.98))
                    if fy == CURRENT_FY:
                        sup.append((cids[ck], t["code"], fy, s_seats, enrolled, 0, 0, 0, 0, int(enrolled * t["women_share"])))
                        continue
                    completed = int(enrolled * rng.uniform(0.8, 0.92))
                    certified = int(completed * rng.uniform(0.82, 0.93))
                    place_rate = float(np.clip(0.72 * balance ** 0.45, 0.18, 0.93))
                    placed = int(certified * place_rate)
                    wage = int(t["entry_wage"] * (1.055 ** fy_i) * float(np.clip(balance, 0.4, 2.5)) ** 0.18 * rng.uniform(0.96, 1.04))
                    women = int(enrolled * float(np.clip(t["women_share"] * rng.uniform(0.8, 1.2), 0, 1)))
                    sup.append((cids[ck], t["code"], fy, s_seats, enrolled, completed, certified, placed, wage, women))
    c.executemany("INSERT INTO supply VALUES(?,?,?,?,?,?,?,?,?,?)", sup)

    # ---------- migration corridors ----------
    dest_lgd = {n: districts[idx_of[n]]["lgd"] for n in catalog.MIGRANT_DESTINATIONS}
    mig = {}
    for i, d in enumerate(districts):
        hub = STATE_HUB[d["state"]]
        for sec, sf in MIGRATION_SECTOR.items():
            p = catalog.MIGRANT_ORIGINS.get(d["district"], 0.0)
            if p:
                total = min(0.6, p * sf * 0.85)
                weights = dict(catalog.MIGRANT_DESTINATIONS)
                weights[hub] = weights.get(hub, 0) + 0.2
                z = sum(weights.values())
                for dn, w in weights.items():
                    if dn != d["district"]:
                        key = (d["lgd"], districts[idx_of[dn]]["lgd"], sec)
                        mig[key] = mig.get(key, 0) + total * w / z
            if d["district"] != hub and d["district"] not in dest_lgd:
                key = (d["lgd"], districts[idx_of[hub]]["lgd"], sec)
                # generic pull of the state hub, diluted in states with many districts
                n_state = sum(1 for x in districts if x["state"] == d["state"])
                mig[key] = mig.get(key, 0) + 0.06 * sf * min(1.0, 30 / n_state)
    c.executemany("INSERT INTO migration VALUES(?,?,?,?)", [(*k, round(v, 4)) for k, v in mig.items() if v >= 0.004])

    # ---------- raw postings sample (text) ----------
    generate_postings(c, rng, districts, trades, truth, cov_portal)
    return {"districts": nd, "trades": nt, "months": nm, "signals": len(sig), "centres": len(centres), "supply_rows": len(sup), "official_anchor": anchor}


def generate_postings(c, rng, districts, trades, truth, cov_portal):
    nm = len(PERIODS)
    window = list(range(nm - 12, nm))
    weight = (truth[:, :, window] * cov_portal[:, :, None]).ravel()
    picks = rng.choice(weight.size, size=6200, replace=True, p=weight / weight.sum())
    nd, nt = truth.shape[:2]
    out = []
    ghosts = []
    for pick in picks:
        i, j, mi = np.unravel_index(pick, (nd, nt, len(window)))
        d, t = districts[i], trades[j]
        m = window[mi]
        day = int(rng.integers(1, 28))
        posted = f"{PERIODS[m]}-{day:02d}"
        qp, market = catalog.SKILLS[t["code"]]
        progress = mi / 11
        skills = []
        for s in market:
            p = 0.55 if s in qp else 0.12 + 0.48 * progress
            if rng.random() < p:
                skills.append(s)
        if not skills:
            skills = [market[0]]
        title = str(rng.choice(catalog.TITLE_VARIANTS[t["code"]]))
        if rng.random() < 0.1:  # vague, generic listings are common and genuinely hard to code
            title = str(rng.choice(["Technician", "Helper", "Executive", "Operator", "Associate", "Staff Required", "Field Worker"]))
            skills = skills[:1]
        r = rng.random()
        if r < 0.15:
            title += " - Urgent Hiring"
        elif r < 0.25:
            title += f" ({d['district']})"
        elif r < 0.32:
            title = title.lower() + " chahiye"
        elif r < 0.38:
            title = title.upper()
        elif r < 0.44 and len(title) > 6:
            k = int(rng.integers(1, len(title) - 2))
            title = title[:k] + title[k + 1:]  # typo
        employer = f"{rng.choice(EMPLOYER_PREFIX)} {rng.choice(EMPLOYER_SUFFIX[t['sector']])}"
        salary = int(t["entry_wage"] * rng.uniform(0.85, 1.35) / 500) * 500
        desc = f"{employer} is hiring for {title} in {d['district']}, {d['state']}. Skills required: {', '.join(skills)}. Salary Rs {salary}/month. Experience 0-2 years."
        gold = t["code"] if rng.random() < 0.35 else None
        portal = str(rng.choice(PORTALS))
        out.append([portal, posted, d["lgd"], employer, title, desc, salary, gold, t["code"]])
        if rng.random() < (0.45 if t["sector"] == "IT" else 0.28):  # cross-posted near-duplicate (matches feed duplication)
            alt = [p for p in PORTALS if p != portal]
            d2 = min(28, day + int(rng.integers(0, 8)))
            out.append([str(rng.choice(alt)), f"{PERIODS[m]}-{d2:02d}", d["lgd"], employer, title, desc.replace("Experience 0-2 years.", "Freshers can apply."), salary, None, t["code"]])
        if rng.random() < 0.015:
            ghosts.append(out[-1])
    for g in ghosts:  # repeatedly re-posted, never-filled listings
        for k in range(1, 4):
            y, m = map(int, g[1][:7].split("-"))
            p2 = add_months(f"{y:04d}-{m:02d}", -k)
            if p2 >= PERIODS[-12]:
                out.append([g[0], p2 + g[1][7:], g[2], g[3], g[4], g[5], g[6], None, g[8]])
    out.sort(key=lambda r: r[1])
    c.executemany("INSERT INTO postings(portal,posted_on,lgd,employer,raw_title,description,salary,gold_code,eval_code) VALUES(?,?,?,?,?,?,?,?,?)", out)


def seed(reset: bool = False) -> dict | None:
    c = connect()
    try:
        if reset:
            non_synthetic = c.execute("SELECT COUNT(*) FROM sources WHERE source_type='imported'").fetchone()[0]
            if non_synthetic:
                raise RuntimeError("Refusing reset: database contains non-demo sources.")
            for table in ["alerts", "gaps", "backtests", "forecasts", "source_weights", "uldi", "pipeline_runs", "scenarios", "synthetic_truth", "migration", "supply", "centres",
                          "investments", "postings", "plfs", "official_stats", "benchmarks", "signals", "sources", "qp_skills", "trades", "districts"]:
                c.execute(f"DELETE FROM {table}")
            c.commit()
        if c.execute("SELECT COUNT(*) FROM districts").fetchone()[0]:
            official.load(c)  # pick up any update to the official statistics file
            c.commit()
            return None
        summary = generate(c, np.random.default_rng(SEED))
        summary["official_rows"] = official.load(c)
        c.commit()
        return summary
    finally:
        c.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true")
    print(seed(p.parse_args().reset))
