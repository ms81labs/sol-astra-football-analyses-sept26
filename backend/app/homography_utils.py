"""Pure math helpers — no cv2 or YOLO dependency. Importable in all environments."""
from __future__ import annotations

import numpy as np

PITCH_WIDTH = 100.0
PITCH_HEIGHT = 100.0


def build_homography_from_points(points):
    """Build a 3x3 homography matrix from 4 source points → unit pitch rectangle.

    Raises
    ------
    ValueError
        When fewer than 4 points are given or points are degenerate (collinear /
        coincident), making it impossible to compute a valid homography.
    """
    if len(points) < 4:
        raise ValueError("homography_points must contain exactly 4 points.")
    src_pts = np.array(points, dtype=np.float32)
    dst_pts = np.array(
        [
            [0, 0],
            [PITCH_WIDTH, 0],
            [PITCH_WIDTH, PITCH_HEIGHT],
            [0, PITCH_HEIGHT],
        ],
        dtype=np.float32,
    )
    result = cv2_findHomography_stub(src_pts, dst_pts)
    if result is None:
        raise ValueError(
            "Failed to compute homography from the provided points — "
            "they may be degenerate (collinear or coincident)."
        )
    H, _ = result
    return H


def point_to_pitch(H, x, y):
    """Project a point from camera space to 2D pitch space using Homography."""
    pt = np.array([x, y, 1.0])
    projected = H.dot(pt)
    projected /= projected[2]
    return float(projected[0]), float(projected[1])


# ---------------------------------------------------------------------------
# Internal stub — DLT homography without requiring opencv
# ---------------------------------------------------------------------------

def cv2_findHomography_stub(src, dst, _method=0, _ransacReprojThreshold=3.0, _maxIters=2000, confidence=0.995):
    """Return (H, mask) for valid non-degenerate quadrilaterals, None otherwise."""
    if len(src) < 4 or len(dst) < 4:
        return None
    src = np.array(src, dtype=np.float64)
    dst = np.array(dst, dtype=np.float64)
    # Degenerate when source points are collinear (zero signed area)
    area = abs(
        src[0][0] * (src[1][1] - src[2][1])
        + src[1][0] * (src[2][1] - src[0][1])
        + src[2][0] * (src[0][1] - src[1][1])
    )
    if area < 1e-6:
        return None
    # Direct Linear Transform (DLT) for homography
    n = len(src)
    A = np.zeros((2 * n, 9), dtype=np.float64)
    for i in range(n):
        sx, sy = src[i]
        dx, dy = dst[i]
        A[2 * i] = [-sx, -sy, -1, 0, 0, 0, sx * dx, sy * dx, dx]
        A[2 * i + 1] = [0, 0, 0, -sx, -sy, -1, sx * dy, sy * dy, dy]
    _, _, Vt = np.linalg.svd(A)
    H = Vt[-1].reshape(3, 3)
    H /= H[2, 2]
    return H, np.ones(n, dtype=np.uint8)
