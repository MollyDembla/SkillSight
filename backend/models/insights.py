"""Decision intelligence built on the gap engine: re-skilling pathways, curriculum drift, centre siting, what-if."""
from __future__ import annotations
import math, re
from collections import Counter, defaultdict
import numpy as np
from .. import catalog
from ..db import FUTURE, PERIODS, add_months, month_index
from . import forecast as F
from .gap import SHORT, SURPLUS, classify


# ---------------- Pivot pathways ----------------
def _overlap(src: str, tgt: str) -> tuple[float, list[str], list[str]]:
    have = set(catalog.SKILLS[src][0])
    need = set(catalog.SKILLS[tgt][1])
    common = sorted(have & need)
    return len(common) / max(1, len(need)), common, sorted(need - have)


def pathways(state: dict, lgd: str | None = None, state_name: str | None = None, limit: int = 50) -> dict:
    frame, g = state["frame"], state["gap"]
    D, S, gr = g["D"]["p50"], g["S"], g["gr"]
    trades = frame.trades
    pairs = []
    for i, d in enumerate(frame.districts):
        if lgd and d["lgd"] != lgd:
            continue
        if state_name and d["state"] != state_name:
            continue
        surplus = [(j, S[i, j] - D[i, j]) for j in range(len(trades)) if gr[i, j] >= SURPLUS]
        short = [(j, D[i, j] - S[i, j]) for j in range(len(trades)) if gr[i, j] <= SHORT]
        for js, sv in surplus:
            for jt, tv in short:
                ov, common, missing = _overlap(trades[js]["code"], trades[jt]["code"])
                if ov < 0.25 or abs(trades[js]["nsqf_level"] - trades[jt]["nsqf_level"]) > 1:
                    continue
                hours = int(round(trades[jt]["hours"] * (1 - ov) * 0.6 / 10) * 10)
                absorb = min(sv, tv) * min(1.0, ov * 1.6)
                cost = hours * trades[jt]["cost_per_seat"] / trades[jt]["hours"]
                pairs.append({"lgd": d["lgd"], "district": d["district"], "state": d["state"],
                              "from_code": trades[js]["code"], "from_trade": trades[js]["title"], "to_code": trades[jt]["code"], "to_trade": trades[jt]["title"],
                              "skill_overlap": round(ov, 2), "shared_skills": common, "bridge_skills": missing, "bridge_hours": hours,
                              "bridge_cost_per_candidate": round(cost), "surplus": round(sv), "shortage": round(tv), "absorbable": round(absorb),
                              "savings_vs_fresh_training": round(trades[jt]["cost_per_seat"] - cost)})
    pairs.sort(key=lambda p: -p["absorbable"])
    agg = defaultdict(lambda: {"absorbable": 0, "districts": 0})
    for p in pairs:
        k = (p["from_trade"], p["to_trade"], p["skill_overlap"], p["bridge_hours"])
        agg[k]["absorbable"] += p["absorbable"]
        agg[k]["districts"] += 1
    summary = [{"from_trade": k[0], "to_trade": k[1], "skill_overlap": k[2], "bridge_hours": k[3], **v} for k, v in sorted(agg.items(), key=lambda kv: -kv[1]["absorbable"])]
    return {"total_absorbable": round(sum(p["absorbable"] for p in pairs)), "pathways": pairs[:limit], "by_pair": summary[:20]}


# ---------------- Curriculum drift ----------------
ALL_SKILLS = sorted({s for qp, mk in catalog.SKILLS.values() for s in qp + mk}, key=len, reverse=True)
_SKILL_RE = re.compile("|".join(re.escape(s) for s in ALL_SKILLS))


def extract_skills(text: str) -> list[str]:
    return sorted(set(_SKILL_RE.findall((text or "").lower())))


def curriculum(c, trade_code: str | None = None) -> list[dict]:
    rows = c.execute("SELECT nco_code, posted_on, description FROM postings WHERE nco_code IS NOT NULL AND ghost = 0").fetchall()
    months = sorted({r["posted_on"][:7] for r in rows})
    split = months[len(months) // 2] if months else ""
    by_trade = defaultdict(lambda: {"early": Counter(), "recent": Counter(), "n_early": 0, "n_recent": 0})
    for r in rows:
        b = by_trade[r["nco_code"]]
        part = "recent" if r["posted_on"][:7] >= split else "early"
        b[f"n_{part}"] += 1
        b[part].update(extract_skills(r["description"]))
    out = []
    for t in catalog.trades():
        if trade_code and t["code"] != trade_code:
            continue
        b = by_trade.get(t["code"])
        if not b or b["n_recent"] == 0:
            continue
        qp = set(catalog.SKILLS[t["code"]][0])
        skills = []
        for s in set(b["recent"]) | set(b["early"]) | qp:
            share_r = b["recent"][s] / b["n_recent"]
            share_e = b["early"][s] / max(1, b["n_early"])
            skills.append({"skill": s, "in_qp": s in qp, "share_recent": round(share_r, 3), "share_early": round(share_e, 3),
                           "growth": round((share_r - share_e) / max(share_e, 0.02), 2)})
        total = sum(b["recent"].values())
        covered = sum(v for k, v in b["recent"].items() if k in qp)
        missing = sorted([s for s in skills if not s["in_qp"] and s["share_recent"] >= 0.15], key=lambda s: -s["share_recent"])
        stale = sorted([s for s in skills if s["in_qp"] and s["share_recent"] < 0.05], key=lambda s: s["share_recent"])
        freshness = covered / max(1, total)
        out.append({"trade_code": t["code"], "trade": t["title"], "qp_code": t["qp_code"], "sector": t["sector"], "postings_analysed": b["n_recent"] + b["n_early"],
                    "freshness_score": round(freshness * 100, 1), "revision_priority": "High" if freshness < 0.6 else ("Medium" if freshness < 0.75 else "Low"),
                    "missing_skills": missing, "stale_skills": stale, "skills": sorted(skills, key=lambda s: -s["share_recent"]),
                    "recommendation": (f"Revise {t['qp_code']}: add NOS/modules for " + ", ".join(s["skill"] for s in missing[:3]) +
                                       (f"; review relevance of {', '.join(s['skill'] for s in stale[:2])}" if stale else "") + ".") if missing else f"{t['qp_code']} aligned with current employer demand."})
    return sorted(out, key=lambda r: r["freshness_score"])


# ---------------- Centre siting ----------------
def _haversine(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def siting(c, state: dict, state_name: str | None = None) -> list[dict]:
    frame, g = state["frame"], state["gap"]
    sup = g["supply"]
    seats = sup["A"]["seats"][-1]
    conv = np.maximum(sup["enrol_rate"] * sup["yield"], 0.3)
    D, S, gr = g["D"]["p50"], g["S"], g["gr"]
    centres = defaultdict(list)
    for r in c.execute("SELECT id, lgd, name, lat, lon, capacity, scheme FROM centres"):
        centres[r["lgd"]].append(dict(r))
    out = []
    for i, d in enumerate(frame.districts):
        if state_name and d["state"] != state_name:
            continue
        need_t = np.where(gr[i] <= SHORT, np.maximum(D[i] - S[i], 0) / conv[i], 0)
        free_t = np.where(gr[i] >= SURPLUS, np.minimum(seats[i], np.maximum(S[i] - 1.1 * D[i], 0) / conv[i]), 0)
        cap = sum(x["capacity"] for x in centres[d["lgd"]])
        spare = max(0.0, cap - seats[i].sum())
        need, repurpose = float(need_t.sum()), float(free_t.sum())
        net_new = max(0.0, need - spare - repurpose)
        nearest = min((_haversine(d["lat"], d["lon"], x["lat"], x["lon"]) for x in centres[d["lgd"]]), default=99)
        score = net_new * (1.3 if d["aspirational"] else 1.0) * (1 + min(1.0, nearest / 40))
        top_short = [frame.trades[j]["title"] for j in np.argsort(-need_t)[:3] if need_t[j] > 0]
        top_free = [frame.trades[j]["title"] for j in np.argsort(-free_t)[:2] if free_t[j] > 0]
        if net_new >= 100:
            action = f"Sanction new centre(s): ~{int(math.ceil(net_new / 50) * 50)} seats"
        elif repurpose >= 50 and need >= 50:
            action = f"Repurpose ~{int(min(need, repurpose))} seats from {', '.join(top_free) or 'surplus trades'}"
        elif need >= 50:
            action = f"Use spare capacity (~{int(spare)} seats) in existing centres"
        else:
            action = "No capacity action needed"
        out.append({"lgd": d["lgd"], "district": d["district"], "state": d["state"], "lat": d["lat"], "lon": d["lon"], "aspirational": bool(d["aspirational"]),
                    "seats_needed": round(need), "spare_capacity": round(spare), "repurposable_seats": round(repurpose), "net_new_capacity": round(net_new),
                    "centres": len(centres[d["lgd"]]), "nearest_centre_km": round(nearest, 1), "priority_score": round(score), "action": action,
                    "priority_trades": top_short, "repurpose_from": top_free})
    return sorted(out, key=lambda r: -r["priority_score"])


# ---------------- What-if: investment shock ----------------
def simulate_investment(state: dict, lgd: str, sector: str, jobs_ops: int, jobs_build: int, ops_start: str, build_months: int = 9,
                        ramp_months: int = 12, name: str = "Hypothetical project") -> dict:
    frame = state["frame"]
    if lgd not in frame.d_ix:
        raise ValueError("Unknown district")
    if sector not in catalog.SECTORS:
        raise ValueError("Unknown sector")
    origin = len(PERIODS) - 1
    if month_index(ops_start) <= origin - 6:
        raise ValueError("Operations start must be recent or in the future")
    hypo = {"name": name, "lgd": lgd, "sector": sector, "jobs_ops": jobs_ops, "jobs_build": jobs_build, "announced": PERIODS[-1],
            "build_start": add_months(ops_start, -build_months), "ops_start": ops_start, "ramp_months": ramp_months}
    ctx, Y, static = state["ctx"], state["Y"], state["static"]
    n_total = ctx["pipe"].shape[2]
    pipe_new = ctx["pipe"] + F.pipeline_hiring([hypo], frame, n_total, origin)
    i = frame.d_ix[lgd]
    base = F.gbm_predict(ctx["model"], Y, ctx["pipe"], ctx["sidx"], origin, len(FUTURE), static)[i]
    new = F.gbm_predict(ctx["model"], Y, pipe_new, ctx["sidx"], origin, len(FUTURE), static)[i]
    # Learned response is used for shape; the announced hiring itself is a floor on the uplift (the model
    # cannot extrapolate beyond project sizes it has seen).
    direct = (pipe_new - ctx["pipe"])[i, :, origin + 1: origin + 1 + len(FUTURE)]
    delta = np.maximum(new - base, direct * 0.8)
    fc = state["fc"]
    g = state["gap"]
    p50_before = fc["p50"][i]
    p50_after = p50_before + delta
    D_b = p50_before[:, :12].sum(axis=1)
    D_a = p50_after[:, :12].sum(axis=1)
    S = g["S"][i]
    gr_b, gr_a = (S - D_b) / np.maximum(D_b, 1), (S - D_a) / np.maximum(D_a, 1)
    st_b, st_a = classify(gr_b), classify(gr_a)
    conv = np.maximum(g["supply"]["enrol_rate"][i] * g["supply"]["yield"][i], 0.3)
    rows = []
    for j, t in enumerate(frame.trades):
        if abs(D_a[j] - D_b[j]) < 0.5:
            continue
        extra = max(0.0, D_a[j] - max(S[j], D_b[j])) / conv[j]
        rows.append({"trade_code": t["code"], "trade": t["title"], "sector": t["sector"], "demand_before": round(float(D_b[j])), "demand_after": round(float(D_a[j])),
                     "supply": round(float(S[j])), "gap_ratio_before": round(float(gr_b[j]), 3), "gap_ratio_after": round(float(gr_a[j]), 3),
                     "status_before": str(st_b[j]), "status_after": str(st_a[j]), "extra_seats_needed": int(math.ceil(extra / 5) * 5),
                     "extra_cost": int(math.ceil(extra / 5) * 5 * t["cost_per_seat"])})
    rows.sort(key=lambda r: -(r["demand_after"] - r["demand_before"]))
    affected = [frame.t_ix[r["trade_code"]] for r in rows]
    series = [{"period": FUTURE[h], "before": round(float(p50_before[affected, h].sum())), "after": round(float(p50_after[affected, h].sum()))} for h in range(len(FUTURE))]
    d = frame.districts[i]
    return {"project": hypo, "district": d["district"], "state": d["state"], "trades": rows, "series": series,
            "total_extra_seats": sum(r["extra_seats_needed"] for r in rows), "total_extra_cost": sum(r["extra_cost"] for r in rows),
            "new_shortages": [r["trade"] for r in rows if r["status_after"] in ("Shortage", "Acute shortage") and r["status_before"] not in ("Shortage", "Acute shortage")],
            "method": "Global GBM re-forecast with the hypothetical project in the investment-pipeline features; announced hiring used as a floor on uplift."}
