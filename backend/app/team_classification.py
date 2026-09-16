from __future__ import annotations

from collections import defaultdict

import numpy as np

from .schemas import ColorClusterResult, ColorClusterSummary


def _track_feature_matrix(track_colors: dict[int, list[tuple[float, float, float]]]) -> tuple[list[int], np.ndarray]:
    track_ids = sorted(track_colors)
    vectors = []
    for track_id in track_ids:
        samples = np.array(track_colors[track_id], dtype=float)
        vectors.append(samples.mean(axis=0))
    return track_ids, np.array(vectors, dtype=float)


def _initialize_centroids(vectors: np.ndarray, cluster_count: int) -> np.ndarray:
    centroids = [vectors[0]]
    while len(centroids) < cluster_count:
        distances = np.array(
            [min(np.linalg.norm(vector - centroid) for centroid in centroids) for vector in vectors]
        )
        centroids.append(vectors[int(distances.argmax())])
    return np.array(centroids, dtype=float)


def cluster_track_colors(
    track_colors: dict[int, list[tuple[float, float, float]]],
    cluster_count: int = 2,
    max_iterations: int = 20,
) -> ColorClusterResult:
    if not track_colors:
        return ColorClusterResult(trackToCluster={}, clusters=[])

    track_ids, vectors = _track_feature_matrix(track_colors)
    cluster_count = max(1, min(cluster_count, len(track_ids)))
    centroids = _initialize_centroids(vectors, cluster_count)

    assignments = np.zeros(len(track_ids), dtype=int)
    for _ in range(max_iterations):
        distances = np.linalg.norm(vectors[:, None, :] - centroids[None, :, :], axis=2)
        next_assignments = distances.argmin(axis=1)
        if np.array_equal(next_assignments, assignments):
            break
        assignments = next_assignments
        for cluster_index in range(cluster_count):
            members = vectors[assignments == cluster_index]
            if len(members) > 0:
                centroids[cluster_index] = members.mean(axis=0)

    track_to_cluster = {track_id: int(assignments[index]) for index, track_id in enumerate(track_ids)}
    grouped_track_ids: dict[int, list[int]] = defaultdict(list)
    for track_id, cluster_id in track_to_cluster.items():
        grouped_track_ids[cluster_id].append(track_id)

    clusters = [
        ColorClusterSummary(
            clusterId=cluster_id,
            rgbCentroid=[round(value, 2) for value in centroids[cluster_id].tolist()],
            trackIds=grouped_track_ids[cluster_id],
        )
        for cluster_id in sorted(grouped_track_ids)
    ]
    return ColorClusterResult(trackToCluster=track_to_cluster, clusters=clusters)


def cluster_result_from_summaries(clusters: list[ColorClusterSummary]) -> ColorClusterResult:
    track_to_cluster: dict[int, int] = {}
    for cluster in clusters:
        for track_id in cluster.trackIds:
            track_to_cluster[int(track_id)] = cluster.clusterId
    return ColorClusterResult(trackToCluster=track_to_cluster, clusters=clusters)


def classify_player_rows_by_cluster(
    rows: list[dict],
    cluster_result: ColorClusterResult,
    my_team_cluster: int | None,
) -> list[dict]:
    return [classify_player_row_by_cluster(row, cluster_result, my_team_cluster) for row in rows]


def classify_player_row_by_cluster(
    row: dict,
    cluster_result: ColorClusterResult,
    my_team_cluster: int | None,
) -> dict:
    next_row = dict(row)
    if my_team_cluster is not None and next_row.get("Entity_Type") == "player":
        track_id = int(next_row.get("Track_ID", -1))
        cluster_id = cluster_result.trackToCluster.get(track_id)
        if cluster_id is not None:
            next_row["Entity_Type"] = "my_team" if cluster_id == my_team_cluster else "enemy"
    return next_row
