"""Demand-supply gap engine: migration-aware supply, probabilistic gap classes, severity, drivers, alerts."""
from __future__ import annotations
import json
from collections import defaultdict
import numpy as np
from scipy.special import ndtr
from ..db import COMPLETED_FYS, CURRENT_FY, PERIODS, fiscal_year

ABSORPTION = 0.12          # share of registered informal job-seekers realistically absorbable into skilled openings
SHORT, SURPLUS = -0.15, 0.20
ACUTE, OVER = -0.40, 0.60
STATUSES = ["Acute shortage", "Shortage", "Balanced", "Saturating", "Oversupplied"]


def classify(gr: np.ndarray) -> np.ndarray:
    return np.select([gr <= ACUTE, gr <= SHORT, gr < SURPLUS, gr < OVER], STATUSES[:4], STATUSES[4])


def supply_arrays(c, frame) -> dict:
    nd, nt = frame.shape[:2]
    fys = COMPLETED_FYS + [CURRENT_FY]
    f_ix = {fy: k for k, fy in enumerate(fys)}
    A = {k: np.zeros((len(fys), nd, nt)) for k in ["seats", "enrolled", "completed", "certified", "placed", "wage_x_placed", "women"]}
    q = "SELECT ce.lgd, s.trade_code, s.fy, s.seats, s.enrolled, s.completed, s.certified, s.placed, s.avg_wage, s.women FROM supply s JOIN centres ce ON ce.id = s.centre_id"
    for lgd, code, fy, seats, enr, comp, cert, placed, wage, women in c.execute(q):
        k, i, j = f_ix[fy], frame.d_ix[lgd], frame.t_ix[code]
        A["seats"][k, i, j] += seats
        A["enrolled"][k, i, j] += enr
        A["completed"][k, i, j] += comp
        A["certified"][k, i, j] += cert
        A["placed"][k, i, j] += placed
        A["wage_x_placed"][k, i, j] += wage * placed
        A["women"][k, i, j] += women
    done = slice(0, len(COMPLETED_FYS))
    enr = A["enrolled"][done].sum(axis=0)
    cert = A["certified"][done].sum(axis=0)
    trade_yield = cert.sum(axis=0) / np.maximum(enr.sum(axis=0), 1)
    yield_ = np.where(enr > 30, cert / np.maximum(enr, 1), trade_yield[None, :])
    enrol_rate = np.where(A["seats"][-1] > 0, A["enrolled"][-1] / np.maximum(A["seats"][-1], 1), 0.9)
    # migration: out-share per origin x sector and origin->destination matrix per sector
    sec_ix = {s: k for k, s in enumerate(frame.sectors)}
    M = np.zeros((len(frame.sectors), nd, nd))
    for o, d, sec, share in c.execute("SELECT origin_lgd, dest_lgd, sector, share FROM migration"):
        if o in frame.d_ix and d in frame.d_ix and sec in sec_ix:
            M[sec_ix[sec], frame.d_ix[o], frame.d_ix[d]] = share
    out_share = np.stack([M[sec_ix[s]].sum(axis=1) for s in frame.sector_of], axis=1)    # (nd, nt)
    # e-Shram seekers: latest published month
    seekers = np.zeros((nd, nt))
    latest = c.execute("SELECT MAX(s.period) FROM signals s JOIN sources so ON so.id = s.source_id WHERE so.key = 'eshram'").fetchone()[0]
    for lgd, code, v in c.execute("SELECT s.lgd, s.trade_code, s.value FROM signals s JOIN sources so ON so.id = s.source_id WHERE so.key = 'eshram' AND s.period = ?", (latest,)):
        seekers[frame.d_ix[lgd], frame.t_ix[code]] = v
    return {"A": A, "fys": fys, "yield": yield_, "enrol_rate": enrol_rate, "M": M, "sec_ix": sec_ix, "out_share": out_share, "seekers": seekers}


def supply_for(seats: np.ndarray, sup: dict, frame, enrol_rate=None) -> dict:
    """Certified output that reaches each district's labour market from a seat plan (nd, nt)."""
    enrol_rate = sup["enrol_rate"] if enrol_rate is None else enrol_rate
    certified = seats * enrol_rate * sup["yield"]
    outflow = certified * sup["out_share"]
    inflow = np.zeros_like(certified)
    for j, s in enumerate(frame.sector_of):
        inflow[:, j] = sup["M"][sup["sec_ix"][s]].T @ certified[:, j]
    seekers = sup["seekers"] * ABSORPTION
    return {"certified": certified, "outflow": outflow, "inflow": inflow, "seekers": seekers,
            "total": certified - outflow + inflow + seekers}


def compute(c, frame, history, fc, uplift, trust, window_idx, investments, sidx) -> dict:
    """history: ULDI (nd, nt, nm); fc: dict p10/p50/p90 (nd, nt, H); uplift (nd, nt, H); window_idx: horizon indices."""
    nd, nt = frame.shape[:2]
    sup = supply_arrays(c, frame)
    A = sup["A"]
    cur = supply_for(A["seats"][-1], sup, frame)
    S = cur["total"]
    D = {k: fc[k][:, :, window_idx].sum(axis=2) for k in ("p10", "p50", "p90")}
    D_last12 = history[:, :, -12:].sum(axis=2)
    sigma = np.maximum((D["p90"] - D["p10"]) / 2.563, 1e-6)
    gr = (S - D["p50"]) / np.maximum(D["p50"], 1e-6)
    status = classify(gr)
    p_short = 1 - ndtr((S / (1 + SHORT) - D["p50"]) / sigma)           # P(D large enough that GR <= -15%)
    p_surplus = ndtr((S / (1 + SURPLUS) - D["p50"]) / sigma)           # P(D small enough that GR >= +20%)
    # quarter-by-quarter outlook: seasonally adjusted, annualised quarterly demand vs annual supply
    # (so a monsoon dip in construction is not mistaken for saturation)
    from .forecast import _month_of
    quarters = []
    for q in range(4):
        idx = window_idx[q * 3:(q + 1) * 3]
        adj = np.stack([sidx[:, _month_of(len(PERIODS) + h)] for h in idx], axis=-1)[None]   # (1, nt, 3)
        dq = (fc["p50"][:, :, idx] / adj).sum(axis=2) * 4
        sq = np.maximum(((fc["p90"][:, :, idx] - fc["p10"][:, :, idx]) / adj).sum(axis=2) * 4 / 2.563, 1e-6)
        quarters.append({"gr": (S - dq) / np.maximum(dq, 1e-6), "p_short": 1 - ndtr((S / (1 + SHORT) - dq) / sq), "p_surplus": ndtr((S / (1 + SURPLUS) - dq) / sq)})
    # history per completed FY
    fy_of = np.array([fiscal_year(p) for p in PERIODS])
    hist_gr = []
    for k, fy in enumerate(COMPLETED_FYS):
        mm = np.where(fy_of == fy)[0]
        d_fy = history[:, :, mm].sum(axis=2) * 12 / max(1, len(mm))
        s_fy = supply_for(A["seats"][k], sup, frame, enrol_rate=np.where(A["seats"][k] > 0, A["enrolled"][k] / np.maximum(A["seats"][k], 1), 0.9))["total"]
        hist_gr.append((s_fy - d_fy) / np.maximum(d_fy, 1e-6))
    hist_gr = np.stack(hist_gr)                                         # (nfy, nd, nt)
    short_now, surplus_now = gr <= SHORT, gr >= SURPLUS
    persistence = np.where(short_now, (hist_gr <= SHORT).sum(axis=0), np.where(surplus_now, (hist_gr >= SURPLUS).sum(axis=0), 0))
    w_old = A["wage_x_placed"][0] / np.maximum(A["placed"][0], 1)
    w_new = A["wage_x_placed"][2] / np.maximum(A["placed"][2], 1)
    wage_growth = np.where((A["placed"][0] > 5) & (A["placed"][2] > 5), w_new / np.maximum(w_old, 1) - 1, 0.1)
    placement = A["placed"][2] / np.maximum(A["certified"][2], 1)
    growth = D["p50"] / np.maximum(D_last12, 1e-6) - 1

    mag = np.clip(np.abs(gr) / 0.8, 0, 1)
    accel = np.where(short_now & (growth > 0), np.clip(growth / 0.3, 0, 1), np.where(surplus_now & (growth < 0), np.clip(-growth / 0.3, 0, 1), 0))
    wage = np.where(short_now, np.clip((wage_growth - 0.1) / 0.1, 0, 1), np.where(surplus_now, np.clip((0.1 - wage_growth) / 0.1, 0, 1), 0))
    sev = 100 * (0.45 * mag + 0.15 * persistence / 3 + 0.15 * accel + 0.1 * wage + 0.15 * trust)
    sev *= np.where(short_now | surplus_now, 1.0, 0.35)
    sev *= 0.6 + 0.4 * np.clip(np.log10(np.maximum(D["p50"], 1)) / 3, 0, 1)
    sev = np.round(np.clip(sev, 0, 100), 1)

    lead = np.zeros((nd, nt), dtype=int)
    for q in range(3, -1, -1):
        hit = np.where(short_now | (gr < 0), quarters[q]["p_short"] >= 0.6, quarters[q]["p_surplus"] >= 0.6)
        lead = np.where(hit, q + 1, lead)

    invest_sum = uplift[:, :, window_idx].sum(axis=2)
    proj_by_district = defaultdict(list)
    for inv in investments:
        proj_by_district[inv["lgd"]].append(inv)
    seats_prev = A["seats"][-2]
    out_rows = []
    for i, dist in enumerate(frame.districts):
        for j, tr in enumerate(frame.trades):
            drivers = []
            organic = D["p50"][i, j] - D_last12[i, j] - invest_sum[i, j]
            drivers.append({"key": "organic_trend", "label": "Organic demand trend (next 12m vs last 12m)", "value": round(float(organic))})
            if abs(invest_sum[i, j]) >= 1:
                projs = [p for p in proj_by_district.get(dist["lgd"], [])]
                drivers.append({"key": "investment", "label": "Investment hiring waves (net change)", "value": round(float(invest_sum[i, j])),
                                "projects": [p["name"] for p in projs]})
            drivers.append({"key": "seats_change", "label": f"Training seats FY{CURRENT_FY} vs FY{COMPLETED_FYS[-1]}", "value": round(float(A["seats"][-1][i, j] - seats_prev[i, j]))})
            net_mig = cur["inflow"][i, j] - cur["outflow"][i, j]
            if abs(net_mig) >= 1:
                drivers.append({"key": "migration", "label": "Net migration of certified workers", "value": round(float(net_mig))})
            drivers.append({"key": "seekers", "label": "Absorbable e-Shram job-seekers", "value": round(float(cur["seekers"][i, j]))})
            out_rows.append((
                dist["lgd"], tr["code"], round(float(D["p10"][i, j]), 1), round(float(D["p50"][i, j]), 1), round(float(D["p90"][i, j]), 1),
                round(float(D_last12[i, j]), 1), round(float(S[i, j]), 1), round(float(cur["certified"][i, j]), 1), round(float(cur["outflow"][i, j]), 1),
                round(float(cur["inflow"][i, j]), 1), round(float(cur["seekers"][i, j]), 1), round(float(A["seats"][-1][i, j])), round(float(S[i, j] - D["p50"][i, j]), 1),
                round(float(gr[i, j]), 4), str(status[i, j]), float(sev[i, j]), round(float(p_short[i, j]), 4), round(float(p_surplus[i, j]), 4),
                int(lead[i, j]) or None, round(float(trust[i, j]), 3), int(persistence[i, j]), round(float(wage_growth[i, j]), 4), round(float(placement[i, j]), 4),
                round(float(invest_sum[i, j]), 1), json.dumps(drivers),
                json.dumps([{"q": q + 1, "gap_ratio": round(float(quarters[q]["gr"][i, j]), 3), "p_shortage": round(float(quarters[q]["p_short"][i, j]), 3), "p_surplus": round(float(quarters[q]["p_surplus"][i, j]), 3)} for q in range(4)]),
                json.dumps([{"fy": fy, "gap_ratio": round(float(hist_gr[k, i, j]), 3)} for k, fy in enumerate(COMPLETED_FYS)]),
            ))
    c.execute("DELETE FROM gaps")
    c.executemany(f"INSERT INTO gaps VALUES({','.join('?' * 27)})", out_rows)
    return {"gr": gr, "status": status, "severity": sev, "p_short": p_short, "p_surplus": p_surplus, "lead": lead,
            "quarters": quarters, "hist_gr": hist_gr, "D": D, "S": S, "supply": sup, "current": cur}


def raise_alerts(c, frame, g) -> dict:
    """Upsert early-warning flags; keeps planner workflow status (acknowledged/assigned) across runs."""
    nd, nt = frame.shape[:2]
    c.execute("UPDATE alerts SET active = 0")
    counts = defaultdict(int)
    for i in range(nd):
        for j in range(nt):
            d50 = g["D"]["p50"][i, j]
            sev = float(g["severity"][i, j])
            gr, lead = float(g["gr"][i, j]), int(g["lead"][i, j])
            qs = g["quarters"]
            found = []
            if d50 >= 60 and sev >= 50 and gr <= ACUTE and g["p_short"][i, j] >= 0.7:
                found.append(("acute_shortage", g["p_short"][i, j], lead))
            if d50 >= 60 and sev >= 50 and gr >= OVER and g["p_surplus"][i, j] >= 0.7:
                found.append(("saturation", g["p_surplus"][i, j], lead))
            # Early warning: not a shortage in the coming quarter, but one is likely in a later quarter.
            if d50 >= 40 and qs[0]["gr"][i, j] > SHORT:
                hit = next((q for q in range(1, 4) if qs[q]["p_short"][i, j] >= 0.6), None)
                if hit is not None:
                    found.append(("emerging_shortage", qs[hit]["p_short"][i, j], hit + 1))
            if d50 >= 40 and qs[0]["gr"][i, j] < SURPLUS:
                hit = next((q for q in range(1, 4) if qs[q]["p_surplus"][i, j] >= 0.6), None)
                if hit is not None:
                    found.append(("emerging_saturation", qs[hit]["p_surplus"][i, j], hit + 1))
            for kind, prob, lead in found:
                _upsert(c, frame, g, i, j, kind, prob, lead, sev, gr, d50)
                counts[kind] += 1
    return dict(counts)


def _upsert(c, frame, g, i, j, kind, prob, lead, sev, gr, d50):
    dist, tr = frame.districts[i], frame.trades[j]
    verb = {"acute_shortage": "acute shortage", "saturation": "saturation", "emerging_shortage": "an emerging shortage", "emerging_saturation": "emerging saturation"}[kind]
    msg = (f"{tr['title']} in {dist['district']} ({dist['state']}): {verb} - forecast demand {d50:,.0f} vs supply {g['S'][i, j]:,.0f} "
           f"over the next 12 months (gap {gr:+.0%}), probability {prob:.0%}" + (f", expected within Q{lead}." if lead else "."))
    c.execute("""INSERT INTO alerts(lgd, trade_code, kind, probability, lead_quarter, severity, message, active, updated_at)
                 VALUES(?,?,?,?,?,?,?,1,CURRENT_TIMESTAMP)
                 ON CONFLICT(lgd, trade_code, kind) DO UPDATE SET probability=excluded.probability, lead_quarter=excluded.lead_quarter,
                 severity=excluded.severity, message=excluded.message, active=1, updated_at=CURRENT_TIMESTAMP""",
              (dist["lgd"], tr["code"], kind, round(float(prob), 3), lead or None, sev, msg))
