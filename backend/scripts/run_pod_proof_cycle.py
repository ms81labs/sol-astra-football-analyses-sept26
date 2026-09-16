"""Read-only compatibility helpers for retired proof-cycle research.

The cloud execution functions fail closed. Git history contains the former
provider implementation.
"""

PLATEAU_BASELINE = {
    "acceptedBallFrames": 101,
    "controlledPossessionFrames": 98,
    "ballTrackViable": False,
    "ballTrackEdgeFrameShare": 0.812,
}


def _retired(*_args: object, **_kwargs: object) -> object:
    raise RuntimeError("historical RunPod proof execution is retired; use Daytona")


_run_pod_local_app_path_proof = _retired
_run_pod_selected_cluster_promotion = _retired


def _slugify(value: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in "-_." else "_" for character in value)
    return cleaned.strip("_") or "retired-proof-cycle"


def _build_plateau_comparison(summary: dict[str, object]) -> dict[str, object]:
    accepted = int(summary.get("acceptedBallFrames", 0) or 0)
    controlled = int(summary.get("controlledPossessionFrames", 0) or 0)
    viable = bool(summary.get("ballTrackViable", False))
    edge_share = float(summary.get("ballTrackEdgeFrameShare", 0.0) or 0.0)
    selected = str(summary.get("selectedRecoveryProfileName") or summary.get("recoveryProfile") or summary.get("recoveryProfileName") or "").strip()
    proposed = str(summary.get("bestProposalProfileName") or "").strip()
    product_success = accepted >= 110 or controlled >= 105 or viable or (
        bool(selected and proposed and selected == proposed)
        and int(summary.get("bestProposalSelectedFrames", 0) or 0) >= 15
    )
    product_beats = product_success or accepted > 101 or controlled > 98 or (
        accepted >= 101 and controlled >= 98 and not viable and edge_share < 0.812
    )
    mechanism = int(summary.get("bestProposalDirectSeedDetectedFrames", 0) or 0) > 0
    return {
        "baseline": dict(PLATEAU_BASELINE),
        "current": {
            "acceptedBallFrames": accepted,
            "controlledPossessionFrames": controlled,
            "ballTrackViable": viable,
            "ballTrackEdgeFrameShare": edge_share,
        },
        "mechanismSuccess": mechanism,
        "productSuccess": product_success,
        "mechanismBeatsPlateau": mechanism,
        "productBeatsPlateau": product_beats,
        "beatsPlateau": product_beats,
    }
