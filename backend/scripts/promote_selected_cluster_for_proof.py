from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT, promote_selected_cluster_benchmark  # noqa: E402
from backend.app.storage import Storage  # noqa: E402


def promote_selected_cluster_for_proof(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    match_id: str,
    cluster_id: int | None = None,
) -> dict[str, object]:
    storage = Storage(storage_root)
    return promote_selected_cluster_benchmark(
        storage,
        match_id,
        cluster_id=cluster_id,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply an explicit myTeamCluster to a saved proof match, rerun it, and print the before/after delta."
    )
    parser.add_argument("--storage-root", default=str(DEFAULT_STORAGE_ROOT))
    parser.add_argument("--match-id", required=True)
    parser.add_argument("--cluster-id", type=int, default=None)
    args = parser.parse_args()

    payload = promote_selected_cluster_for_proof(
        storage_root=Path(args.storage_root),
        match_id=args.match_id,
        cluster_id=args.cluster_id,
    )
    print(json.dumps(payload, separators=(",", ":")))


if __name__ == "__main__":
    main()
