from __future__ import annotations

import math
from typing import Annotated

from pydantic import AfterValidator, BaseModel, model_validator


def _finite(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("value must be finite")
    return value


FiniteFloat = Annotated[float, AfterValidator(_finite)]


def _homography(value: list[list[float]]) -> list[list[float]]:
    if len(value) != 3 or any(len(row) != 3 for row in value):
        raise ValueError("homography must be 3x3")
    matrix = [[_finite(float(item)) for item in row] for row in value]
    determinant = (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )
    if abs(determinant) <= 1e-9:
        raise ValueError("homography must be invertible")
    if matrix[2][2] == 0:
        raise ValueError("homography denominator scale must be nonzero")
    try:
        import numpy as np

        values = np.asarray(matrix, dtype=float)
        if float(np.linalg.cond(values)) >= 1e8 or not np.isfinite(np.linalg.inv(values)).all():
            raise ValueError("homography must be well-conditioned")
    except ImportError:
        pass
    return matrix


Homography3x3 = Annotated[list[list[float]], AfterValidator(_homography)]


class Interval(BaseModel):
    start: FiniteFloat
    end: FiniteFloat | None = None

    @model_validator(mode="after")
    def ordered(self):
        if self.end is not None and self.start > self.end:
            raise ValueError("interval start must not exceed end")
        return self
