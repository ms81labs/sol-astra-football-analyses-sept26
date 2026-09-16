"""
Automated pitch homography detection using line detection and geometric inference.
Detects pitch markings to compute the 2D homography matrix without manual clicks.
Falls back to manual point selection on failure.
"""
import cv2
import numpy as np
from typing import Optional


# Standard pitch dimensions (FIFA standard in meters)
PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0

# Pitch markings relative dimensions (fraction of pitch length/width)
PENALTY_AREA_WIDTH = 40.32  # fraction of pitch width from line
PENALTY_AREA_LENGTH = 16.5   # fraction of pitch length from goal line
SIX_YARD_LENGTH = 5.5       # fraction of pitch length from goal line


def _line_confidence(line: tuple) -> float:
    """Return the precomputed confidence/length score for a detected line."""
    return float(line[4])


def _horizontal_midpoint(line: tuple) -> float:
    """Return the average y-position for a detected horizontal-ish line."""
    return (line[1] + line[3]) / 2


def _vertical_midpoint(line: tuple) -> float:
    """Return the average x-position for a detected vertical-ish line."""
    return (line[0] + line[2]) / 2


def _edge_detect(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Detect edges using Canny on multiple thresholds for robustness."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.bilateralFilter(gray, 9, 75, 75)
    edges = cv2.Canny(blurred, 50, 150, apertureSize=3)
    return edges, blurred


def _find_lines(edges: np.ndarray, frame_shape: tuple[int, int]) -> list:
    """Find line segments using probabilistic Hough transform."""
    min_len = max(frame_shape) // 10
    max_gap = max(frame_shape) // 20
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=60,
        minLineLength=min_len,
        maxLineGap=max_gap
    )
    return lines if lines is not None else []


def _classify_lines(lines: list, min_confidence: float = 0.15) -> dict:
    """
    Classify detected lines into horizontal, vertical, and diagonal.
    Filters out noise using confidence based on line length vs frame diagonal.
    """
    if len(lines) == 0:
        return {"horizontal": [], "vertical": [], "diagonal": []}

    h, w = cv2.minEnclosingCircle(np.array([[0, 0]]))[1], 1
    frame_diag = np.sqrt(h**2 + w**2) if hasattr(cv2, 'minEnclosingCircle') else np.sqrt(900**2 + 600**2)

    # Estimate frame diagonal from any line we have
    if len(lines) > 0:
        sample = lines[0][0]
        frame_diag = np.sqrt((sample[2] - sample[0])**2 + (sample[3] - sample[1])**2) * 3

    min_len = frame_diag * min_confidence

    horizontal, vertical, diagonal = [], [], []

    for line in lines:
        x1, y1, x2, y2 = line[0]
        dx, dy = x2 - x1, y2 - y1
        length = np.sqrt(dx**2 + dy**2)

        if length < min_len:
            continue

        angle = abs(np.arctan2(dy, dx) * 180 / np.pi)

        # Classify: ~0° or ~180° = horizontal, ~90° = vertical
        if angle < 20 or angle > 160:
            horizontal.append((x1, y1, x2, y2, length))
        elif 70 < angle < 110:
            vertical.append((x1, y1, x2, y2, length))
        else:
            diagonal.append((x1, y1, x2, y2, length))

    # Sort by length (confidence), descending
    horizontal.sort(key=_line_confidence, reverse=True)
    vertical.sort(key=_line_confidence, reverse=True)

    return {"horizontal": horizontal, "vertical": vertical, "diagonal": diagonal}


def _cluster_lines_by_position(lines: list, axis: str, tolerance: float = 0.04) -> list:
    """
    Cluster lines by their position along the perpendicular axis.
    Returns representative lines for each cluster.
    """
    if len(lines) == 0:
        return []

    # For horizontal lines: cluster by y-coordinate
    # For vertical lines: cluster by x-coordinate
    if axis == "horizontal":
        pos_key = _horizontal_midpoint
    else:
        pos_key = _vertical_midpoint

    sorted_lines = sorted(lines, key=pos_key)
    clusters = []
    current_cluster = [sorted_lines[0]]
    current_pos = pos_key(sorted_lines[0])

    for line in sorted_lines[1:]:
        line_pos = pos_key(line)
        if abs(line_pos - current_pos) / max(current_pos, 1) < tolerance:
            current_cluster.append(line)
        else:
            clusters.append(current_cluster)
            current_cluster = [line]
            current_pos = line_pos
    clusters.append(current_cluster)

    # Return the longest line from each cluster
    result = []
    for cluster in clusters:
        best = max(cluster, key=_line_confidence)
        result.append(best)

    return result


def _line_intersection(l1: tuple, l2: tuple) -> Optional[tuple[float, float]]:
    """
    Find intersection point between two line segments.
    l1, l2 are (x1, y1, x2, y2).
    Returns (x, y) or None if parallel.
    """
    x1, y1, x2, y2 = l1[:4]
    x3, y3, x4, y4 = l2[:4]

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-6:
        return None

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom

    if 0 <= t <= 1 and 0 <= u <= 1:
        x = x1 + t * (x2 - x1)
        y = y1 + t * (y2 - y1)
        return (float(x), float(y))
    return None


def _score_corners(corners: list, frame_shape: tuple[int, int]) -> float:
    """
    Score a set of 4 corner points by geometric quality.
    Higher score = better quadrilateral (more like a rectangle).
    """
    if len(corners) != 4:
        return 0.0

    h, w = frame_shape[:2]

    # Check all corners are within frame
    for cx, cy in corners:
        if cx < -w * 0.1 or cx > w * 1.1 or cy < -h * 0.1 or cy > h * 1.1:
            return 0.0

    # Sort corners: TL, TR, BR, BL by position
    pts = sorted(corners, key=lambda p: (p[1], p[0]))
    top = sorted(pts[:2], key=lambda p: p[0])
    bot = sorted(pts[2:], key=lambda p: p[0])
    tl, tr, bl, br = top[0], top[1], bot[0], bot[1]

    # Compute side lengths
    def dist(a, b):
        return np.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)

    widths = [dist(tl, tr), dist(bl, br)]
    heights = [dist(tl, bl), dist(tr, br)]
    diag1 = dist(tl, br)
    diag2 = dist(tr, bl)

    # Score: prefer nearly-equal opposite sides and nearly-equal diagonals
    width_ratio = min(widths) / max(widths) if max(widths) > 0 else 0
    height_ratio = min(heights) / max(heights) if max(heights) > 0 else 0
    diag_ratio = min(diag1, diag2) / max(diag1, diag2) if max(diag1, diag2) > 0 else 0

    # Penalize if corners are too close together (too small an area)
    area = 0.5 * abs(
        (tr[0] - tl[0]) * (bl[1] - tl[1]) - (tl[0] - bl[0]) * (tr[1] - tl[1])
    )
    area_ratio = area / (w * h)

    return (width_ratio * 0.3 + height_ratio * 0.3 + diag_ratio * 0.2 + min(area_ratio * 5, 0.2)) / 1.0


def detect_pitch_corners(frame: np.ndarray, _fallback_fn=None) -> Optional[list]:
    """
    Detect the 4 pitch corner points from a video frame using line detection.

    Strategy:
    1. Detect edges with Canny
    2. Find line segments with Hough transform
    3. Classify into horizontal and vertical lines
    4. Cluster by position to find distinct lines at different heights/sides
    5. Find intersections to get corner candidates
    6. Score and return the best 4 corners

    Returns:
        List of 4 corner points as [[x, y], ...] in pixel coordinates,
        or None if detection fails (caller should use fallback).

    Args:
        frame: BGR image (OpenCV format)
        fallback_fn: optional function to call if auto-detection fails
    """
    if frame is None or frame.size == 0:
        return None

    edges, blurred = _edge_detect(frame)
    h, w = frame.shape[:2]

    lines = _find_lines(edges, (h, w))
    classified = _classify_lines(lines, min_confidence=0.12)

    horizontal = classified["horizontal"]
    vertical = classified["vertical"]

    if len(horizontal) < 2 or len(vertical) < 2:
        return None

    # Cluster to get distinct lines at different positions
    h_lines = _cluster_lines_by_position(horizontal, "horizontal", tolerance=0.05)
    v_lines = _cluster_lines_by_position(vertical, "vertical", tolerance=0.05)

    # Keep top candidates
    h_lines = h_lines[:4]
    v_lines = v_lines[:4]

    if len(h_lines) < 2 or len(v_lines) < 2:
        return None

    # Find all intersections
    intersections = []
    for hl in h_lines:
        for vl in v_lines:
            pt = _line_intersection(hl, vl)
            if pt:
                intersections.append(pt)

    if len(intersections) < 4:
        return None

    # Score all possible quadrilaterals
    best_score = 0.0
    best_corners = None

    # Try using the outermost horizontal and vertical lines to form a rectangle
    # Sort horizontals by y (top to bottom)
    sorted_h = sorted(h_lines, key=_horizontal_midpoint)
    # Sort verticals by x (left to right)
    sorted_v = sorted(v_lines, key=_vertical_midpoint)

    if len(sorted_h) >= 2 and len(sorted_v) >= 2:
        # Use top-most and bottom-most horizontals, left-most and right-most verticals
        for hi, top_line in enumerate(sorted_h):
            for bottom_line in sorted_h[hi + 1:]:
                for vi, left_line in enumerate(sorted_v):
                    for right_line in sorted_v[vi + 1:]:
                        corners = []
                        for hline in [top_line, bottom_line]:
                            for vline in [left_line, right_line]:
                                pt = _line_intersection(hline, vline)
                                if pt:
                                    corners.append(pt)
                                    break
                                corners.append(None)
                            if len(corners) < 4:
                                corners = []
                                break

                        if len(corners) == 4 and all(c is not None for c in corners):
                            score = _score_corners(corners, (h, w))
                            if score > best_score:
                                best_score = score
                                best_corners = corners

    # Also try finding penalty box (common in football video)
    if best_score < 0.6 and len(sorted_h) >= 2 and len(sorted_v) >= 2:
        # Try to find penalty area lines
        # The penalty area is a rectangle: 40.32m wide x 16.5m deep
        # In pixel coords, we look for lines that could be penalty area boundaries
        penalty_corners = _find_penalty_area_corners(sorted_h, sorted_v, (h, w))
        if penalty_corners:
            score = _score_corners(penalty_corners, (h, w))
            if score > best_score:
                best_score = score
                best_corners = penalty_corners

    if best_score < 0.3:
        return None

    return [[int(c[0]), int(c[1])] for c in best_corners]


def _find_penalty_area_corners(h_lines: list, v_lines: list, frame_shape: tuple) -> Optional[list]:
    """
    Find penalty area corners by looking for the characteristic rectangular
    pattern of the penalty area (large rectangle near center of frame).
    """
    h, w = frame_shape[:2]

    if len(h_lines) < 2 or len(v_lines) < 2:
        return None

    # Penalty area: one horizontal near top (goal line), one horizontal lower (penalty area line)
    # Two vertical lines at the sides of the penalty area
    sorted_h = sorted(h_lines, key=_horizontal_midpoint)
    # Find the line closest to the center horizontal (likely penalty area line)
    center_y = h / 2
    penalty_line = min(sorted_h, key=lambda line: abs(_horizontal_midpoint(line) - center_y * 1.3))
    goal_line = min(sorted_h, key=lambda line: abs(_horizontal_midpoint(line) - center_y))

    # The penalty area width in pixels (approximate, based on typical 16.5m / 40.32m ratio)
    # Look for vertical lines that intersect both the penalty line and goal line
    v_by_x = sorted(v_lines, key=_vertical_midpoint)

    best_corners = None
    best_corners_score = 0.0

    for vi, left_v in enumerate(v_by_x):
        for right_v in v_by_x[vi + 1:]:
            corners = []
            for hline in [goal_line, penalty_line]:
                for vline in [left_v, right_v]:
                    pt = _line_intersection(hline, vline)
                    if pt:
                        corners.append(pt)
            if len(corners) == 4:
                score = _score_corners(corners, frame_shape)
                if score > best_corners_score:
                    best_corners_score = score
                    best_corners = corners

    return best_corners


def compute_pitch_homography(corners: list, pitch_width: float = 100.0, pitch_height: float = 100.0) -> np.ndarray:
    """
    Compute homography from detected pixel corners to pitch coordinates (0-100 scale).

    Args:
        corners: 4 corner points as [[x, y], ...] in pixel coordinates
                  Expected order: TL, TR, BR, BL
        pitch_width: horizontal output scale (canonical pitch coordinates default to 0-100)
        pitch_height: vertical output scale (canonical pitch coordinates default to 0-100)

    Returns:
        3x3 homography matrix
    """
    src_pts = np.array(corners, dtype=np.float32)
    # Standard goal-left orientation: TL, TR, BR, BL -> (0,0), (w,0), (w,h), (0,h)
    dst_pts = np.array([
        [0, 0],
        [pitch_width, 0],
        [pitch_width, pitch_height],
        [0, pitch_height]
    ], dtype=np.float32)

    H, _ = cv2.findHomography(src_pts, dst_pts)
    if H is None:
        raise ValueError("Could not compute homography from detected corners")
    return H


def detect_and_compute_homography(frame: np.ndarray, pitch_width: float = 100.0, pitch_height: float = 100.0) -> tuple[Optional[np.ndarray], bool]:
    """
    Full auto-detection pipeline: find pitch corners and compute homography.

    Returns:
        (homography_matrix, was_auto) where was_auto=True means auto-detection succeeded
    """
    corners = detect_pitch_corners(frame)
    if corners is None:
        return None, False

    try:
        H = compute_pitch_homography(corners, pitch_width, pitch_height)
        return H, True
    except ValueError:
        return None, False


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pitch_detector.py <video_path>")
        print("       python pitch_detector.py --camera  # Use webcam")
        sys.exit(1)

    if sys.argv[1] == "--camera":
        cap = cv2.VideoCapture(0)
        print("Using webcam. Press SPACE to capture frame and detect pitch.")
    else:
        cap = cv2.VideoCapture(sys.argv[1])

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        display = frame.copy()

        # Try auto-detection
        corners = detect_pitch_corners(frame)
        if corners:
            for i, (cx, cy) in enumerate(corners):
                cv2.circle(display, (cx, cy), 8, (0, 255, 0), -1)
                cv2.putText(display, str(i), (cx + 10, cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Draw quadrilateral
            pts = np.array(corners, np.int32)
            cv2.polylines(display, [pts], True, (0, 255, 0), 2)
            cv2.putText(display, "AUTO DETECTION", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        else:
            cv2.putText(display, "No pitch detected (need manual homography)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        cv2.imshow("Pitch Detection", display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):
            break
        elif key == 27:
            cap.release()
            cv2.destroyAllWindows()
            sys.exit(0)

    cap.release()
    cv2.destroyAllWindows()
