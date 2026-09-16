from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.run_benchmarks import (
    DEFAULT_STORAGE_ROOT,
    probe_selected_cluster_benchmarks,
    summarize_match_benchmark,
    rerun_trimmed_clip_manual,
)
from backend.app.storage import Storage


def _json_model(model: object) -> dict[str, object]:
    return model.model_dump(mode="json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize or rerun the canonical trimmed-clip benchmark.")
    parser.add_argument("--match-id", help="Existing match ID to summarize.")
    parser.add_argument("--storage-root", default=str(DEFAULT_STORAGE_ROOT))
    parser.add_argument(
        "--rerun-manual",
        action="store_true",
        help="Create a fresh manual-calibrated trimmed-clip run and summarize it.",
    )
    parser.add_argument(
        "--probe-clusters",
        action="store_true",
        help="Also probe each detected team cluster by reprocessing the saved match with myTeamCluster selected.",
    )
    args = parser.parse_args()

    storage_root = Path(args.storage_root)
    payload: dict[str, object]

    if args.rerun_manual:
        payload = {
            "fresh": _json_model(rerun_trimmed_clip_manual(storage_root=storage_root)),
        }
        if args.match_id:
            storage = Storage(storage_root)
            payload["saved"] = _json_model(summarize_match_benchmark(storage, args.match_id))
            if args.probe_clusters:
                payload["selectedClusters"] = [
                    _json_model(probe) for probe in probe_selected_cluster_benchmarks(storage, args.match_id)
                ]
    else:
        if not args.match_id:
            parser.error("--match-id is required unless --rerun-manual is provided")
        storage = Storage(storage_root)
        payload = _json_model(summarize_match_benchmark(storage, args.match_id))
        if args.probe_clusters:
            payload = {
                "saved": payload,
                "selectedClusters": [
                    _json_model(probe) for probe in probe_selected_cluster_benchmarks(storage, args.match_id)
                ],
            }

    print(json.dumps(payload, separators=(",", ":")))


if __name__ == "__main__":
    main()
