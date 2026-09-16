"""Minimal local compatibility shim for Ultralytics' lap dependency.

This repo runs in environments where system-wide pip installs are blocked,
but Ultralytics only requires a tiny subset of the external `lap` package:
`__version__` and `lapjv(...)`.

We provide a scipy-backed fallback so local video tracking can proceed without
attempting an auto-install at runtime.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import linear_sum_assignment

__version__ = "0.5.12"


def lapjv(cost_matrix, extend_cost: bool = True, cost_limit: float = math.inf):
    """Implement thresholded partial assignment with scipy's Hungarian solver.

    Returns `(total_cost, x, y)` where:
    - `x[row] = col` or `-1` when unmatched
    - `y[col] = row` or `-1` when unmatched
    """

    cost = np.asarray(cost_matrix, dtype=float)
    if cost.ndim != 2 or np.isnan(cost).any():
        raise ValueError("cost_matrix must be a two-dimensional matrix without NaN")
    rows, cols = cost.shape
    if not extend_cost and rows != cols:
        raise ValueError("rectangular matrices require extend_cost=True")
    if math.isnan(cost_limit) or cost_limit == -math.inf:
        raise ValueError("cost_limit must be finite or positive infinity")
    if rows == 0 or cols == 0:
        return 0.0, np.full(rows, -1, dtype=int), np.full(cols, -1, dtype=int)

    if math.isfinite(cost_limit):
        # Leaving a row and a column unmatched costs one threshold in total.
        padded = np.full((rows + cols, rows + cols), cost_limit / 2, dtype=float)
        padded[:rows, :cols] = np.where(cost <= cost_limit, cost, np.inf)
        padded[rows:, cols:] = 0
        row_ind, col_ind = linear_sum_assignment(padded)
    else:
        row_ind, col_ind = linear_sum_assignment(cost)
    x = np.full(rows, -1, dtype=int)
    y = np.full(cols, -1, dtype=int)
    total_cost = 0.0

    for row, col in zip(row_ind, col_ind):
        if row >= rows or col >= cols:
            continue
        if math.isfinite(cost_limit) and cost[row, col] > cost_limit:
            continue
        x[row] = col
        y[col] = row
        total_cost += cost[row, col]

    return total_cost, x, y
