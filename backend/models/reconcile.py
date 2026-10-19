"""Hierarchical forecast reconciliation (district -> state -> national), weighted least squares (MinT-diagonal).

Independent forecasts exist for every node (districts from the ensemble; states and the nation from a
damped-trend model on the aggregated series). Reconciliation finds bottom-level forecasts whose sums are
coherent and that stay closest to all base forecasts, weighting each node by the inverse of its forecast
scale (W = diag(level)), which prevents small districts from absorbing large aggregate corrections:

    b~ = (S' W^-1 S)^-1 S' W^-1 y^
"""
from __future__ import annotations
import numpy as np


def summing_matrix(state_of: np.ndarray, states: list[str]) -> np.ndarray:
    nd = len(state_of)
    rows = [np.ones(nd)] + [(state_of == s).astype(float) for s in states] + list(np.eye(nd))
    return np.stack(rows)                                            # (1 + ns + nd, nd)


def reconcile(bottom: np.ndarray, states_fc: np.ndarray, national_fc: np.ndarray, state_of, states) -> np.ndarray:
    """bottom: (nd, nt, H); states_fc: (ns, nt, H); national_fc: (nt, H). Returns reconciled bottom (nd, nt, H)."""
    S = summing_matrix(state_of, states)
    nd, nt, H = bottom.shape
    out = np.empty_like(bottom)
    for j in range(nt):
        yhat = np.concatenate([national_fc[j][None, :], states_fc[:, j, :], bottom[:, j, :]])  # (nodes, H)
        w = np.maximum(yhat.mean(axis=1), 1.0)
        Winv = 1 / w
        A = S.T @ (S * Winv[:, None])
        G = np.linalg.solve(A, S.T * Winv[None, :])
        out[:, j, :] = np.maximum(G @ yhat, 0)
    return out


def coherence_error(bottom: np.ndarray, aggregated: np.ndarray) -> float:
    return float(np.abs(bottom.sum(axis=0) - aggregated).max())
