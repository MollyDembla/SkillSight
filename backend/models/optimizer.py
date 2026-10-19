"""Next-cycle training target optimiser (mixed-integer linear programme, HiGHS via scipy.optimize.milp).

Decision: integer seats x[d,t] for the next cycle (FY 2027-28) in the selected scope.
Objective: minimise weighted unmet demand (shortage) + weighted excess supply beyond a 10% buffer,
           plus a tiny cost term so ties go to the cheaper plan.
Subject to: budget, district centre capacity, max change vs current seats (+ room to start new courses),
            minimum women-friendly seat share, no cuts in aspirational districts.
Supply from x: x * enrolment * certification yield * (1 - out-migration) + fixed inflow + absorbable seekers.
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix, hstack, identity, vstack, csr_matrix
from ..db import CYCLE_WINDOW, FUTURE, NEXT_FY


def optimise(state: dict, scope_state: str | None = None, budget_change: float = 0.0, max_change: float = 0.5,
             women_target: float | None = None, protect_aspirational: bool = True, risk: float = 0.0,
             shortage_weight: float = 1.0, surplus_weight: float = 0.6, sector: str | None = None, time_limit: float = 25) -> dict:
    frame, fc, g = state["frame"], state["fc"], state["gap"]
    sup = g["supply"]
    A = sup["A"]
    win = [FUTURE.index(p) for p in CYCLE_WINDOW]
    D_all = fc["p50"][:, :, win].sum(axis=2) + risk * (fc["p90"][:, :, win].sum(axis=2) - fc["p50"][:, :, win].sum(axis=2))
    cur_seats = A["seats"][-1]
    a_all = sup["enrol_rate"] * sup["yield"] * (1 - sup["out_share"])
    a_all = np.where(cur_seats > 0, a_all, 0.9 * sup["yield"] * (1 - sup["out_share"]))
    base_all = g["current"]["inflow"] + g["current"]["seekers"]
    rows_ = np.where(frame.state_of == scope_state)[0] if scope_state else np.arange(len(frame.districts))
    cols_ = np.where(frame.sector_of == sector)[0] if sector else np.arange(len(frame.trades))
    cells = [(i, j) for i in rows_ for j in cols_ if cur_seats[i, j] > 0 or D_all[i, j] >= 30]
    if not cells:
        return {"status": "infeasible", "reason": "No district-trade cells in the selected scope."}
    n = len(cells)
    I = np.array([c[0] for c in cells])
    J = np.array([c[1] for c in cells])
    D = D_all[I, J]
    a = a_all[I, J]
    b = base_all[I, J]
    cur = cur_seats[I, J]
    cost = np.array([frame.trades[j]["cost_per_seat"] for j in J], dtype=float)
    women = np.array([frame.trades[j]["women_share"] for j in J])
    cur_cost = float((cur * cost).sum())
    budget = cur_cost * (1 + budget_change)

    # variables: [x (n) | u (n) | v (n)]
    c_obj = np.concatenate([cost * 1e-7, np.full(n, shortage_weight), np.full(n, surplus_weight)])
    Id = identity(n, format="csr")
    Ad = csr_matrix(np.diag(a)) if n <= 1 else coo_matrix((a, (np.arange(n), np.arange(n))), shape=(n, n)).tocsr()
    Z = csr_matrix((n, n))
    cons = [
        LinearConstraint(hstack([-Ad, -Id, Z]), -np.inf, -(D - b)),             # u >= D - (a x + b)
        LinearConstraint(hstack([Ad, Z, -Id]), -np.inf, 1.1 * D - b),          # v >= a x + b - 1.1 D
        LinearConstraint(hstack([csr_matrix(cost[None, :]), csr_matrix((1, n)), csr_matrix((1, n))]), -np.inf, budget),
    ]
    # district capacity
    cap_rows, cap_ub, asp_rows, asp_lb = [], [], [], []
    caps = state.get("centre_capacity", {})
    for i in np.unique(I):
        mask = (I == i).astype(float)
        cap = max(caps.get(frame.districts[i]["lgd"], 0), cur_seats[i].sum()) * 1.15
        cap_rows.append(mask)
        cap_ub.append(cap)
        if protect_aspirational and frame.districts[i]["aspirational"]:
            asp_rows.append(mask)
            asp_lb.append(cur[I == i].sum())
    cons.append(LinearConstraint(hstack([csr_matrix(np.array(cap_rows)), csr_matrix((len(cap_rows), 2 * n))]), -np.inf, np.array(cap_ub)))
    if asp_rows:
        cons.append(LinearConstraint(hstack([csr_matrix(np.array(asp_rows)), csr_matrix((len(asp_rows), 2 * n))]), np.array(asp_lb), np.inf))
    cur_women = float((cur * women).sum() / max(1, cur.sum()))
    if women_target is None:
        women_target = round(cur_women, 3)       # default: never reduce the share of women-friendly seats
    if women_target > 0:
        cons.append(LinearConstraint(hstack([csr_matrix((women - women_target)[None, :]), csr_matrix((1, 2 * n))]), 0, np.inf))
    lo = np.floor(np.maximum(0, cur * (1 - max_change)))
    hi = np.ceil(cur * (1 + max_change) + np.where(D >= 30, 40, 0))
    bounds = Bounds(np.concatenate([lo, np.zeros(2 * n)]), np.concatenate([hi, np.full(2 * n, np.inf)]))
    integrality = np.concatenate([np.ones(n), np.zeros(2 * n)])
    res = milp(c_obj, constraints=cons, bounds=bounds, integrality=integrality, options={"time_limit": time_limit, "mip_rel_gap": 0.005})
    if res.x is None:
        return {"status": "infeasible", "reason": f"Solver: {res.message}. Relax the budget, women-share target or change limit."}
    x = np.round(res.x[:n])
    s_before = a * cur + b
    s_after = a * x + b
    short_b, short_a = np.maximum(D - s_before, 0), np.maximum(D - s_after, 0)
    sur_b, sur_a = np.maximum(s_before - 1.1 * D, 0), np.maximum(s_after - 1.1 * D, 0)
    out = []
    for k, (i, j) in enumerate(cells):
        dd, tt = frame.districts[i], frame.trades[j]
        out.append({"lgd": dd["lgd"], "state": dd["state"], "district": dd["district"], "aspirational": bool(dd["aspirational"]),
                    "trade_code": tt["code"], "trade": tt["title"], "sector": tt["sector"], "qp_code": tt["qp_code"],
                    "current_seats": int(cur[k]), "recommended_seats": int(x[k]), "change": int(x[k] - cur[k]),
                    "forecast_demand": round(float(D[k])), "supply_before": round(float(s_before[k])), "supply_after": round(float(s_after[k])),
                    "gap_ratio_before": round(float((s_before[k] - D[k]) / max(D[k], 1)), 3), "gap_ratio_after": round(float((s_after[k] - D[k]) / max(D[k], 1)), 3),
                    "cost_change": int((x[k] - cur[k]) * cost[k])})
    out.sort(key=lambda r: -abs(r["change"]))
    return {
        "status": "optimal" if res.status == 0 else "feasible (time limit)",
        "cycle": f"FY {NEXT_FY}", "demand_window": f"{CYCLE_WINDOW[0]} to {CYCLE_WINDOW[-1]}", "scope": scope_state or "All pilot states", "sector": sector,
        "summary": {
            "cells": n, "current_seats": int(cur.sum()), "recommended_seats": int(x.sum()),
            "current_cost": round(cur_cost), "recommended_cost": round(float((x * cost).sum())), "budget": round(budget),
            "unmet_demand_before": round(float(short_b.sum())), "unmet_demand_after": round(float(short_a.sum())),
            "excess_supply_before": round(float(sur_b.sum())), "excess_supply_after": round(float(sur_a.sum())),
            "shortage_closed_pct": round(float(1 - short_a.sum() / max(1, short_b.sum())) * 100, 1),
            "excess_reduced_pct": round(float(1 - sur_a.sum() / max(1, sur_b.sum())) * 100, 1),
            "women_share_before": round(cur_women, 3), "women_share_after": round(float((x * women).sum() / max(1, x.sum())), 3),
            "seats_moved": int(np.abs(x - cur).sum() / 2), "mip_gap": getattr(res, "mip_gap", None),
        },
        "assumptions": {"budget_change": budget_change, "max_change": max_change, "women_share_floor": women_target, "protect_aspirational": protect_aspirational,
                        "risk": risk, "shortage_weight": shortage_weight, "surplus_weight": surplus_weight, "surplus_buffer": 0.1,
                        "new_course_allowance": 40, "capacity_headroom": 0.15, "demand": "reconciled P50 forecast" + (f" + {risk:.0%} of P50-P90 band" if risk else "")},
        "rows": out,
    }
