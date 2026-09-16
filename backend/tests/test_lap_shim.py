import numpy as np

import lap


def test_lapjv_marks_rows_over_cost_limit_unmatched():
    total_cost, x, y = lap.lapjv(
        np.array([
            [1.0, 10.0],
            [10.0, 10.0],
        ]),
        extend_cost=True,
        cost_limit=5.0,
    )

    assert total_cost == 1.0
    assert x.tolist() == [0, -1]
    assert y.tolist() == [0, -1]


def test_lapjv_handles_rectangular_cost_matrix():
    total_cost, x, y = lap.lapjv(
        np.array([
            [1.0, 8.0, 9.0],
            [7.0, 2.0, 9.0],
        ]),
        extend_cost=True,
        cost_limit=5.0,
    )

    assert total_cost == 3.0
    assert x.tolist() == [0, 1]
    assert y.tolist() == [0, 1, -1]
