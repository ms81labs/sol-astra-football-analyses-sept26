"""GA-01 baseline dossier and GA-14 source-bound release dossier."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from .contracts import (
    CAPABILITY_IDS,
    CapabilityEntry,
    StrictModel,
)

INSPECTED_SOURCE_SHA = "5099e1fd50d856a7cd0449f1ef4b1695d8f930c3"
PLAN_VERSION = "1.1"
PROTOCOL_VERSION = "football_analysis_pilot_labels_v3"
INITIAL_CAMERA_PROFILE = "stitched_panoramic_view"
INITIAL_WORKFLOW = "manual_review_plus_declared_camera_setup"


class DossierAsset(StrictModel):
    name: str
    identity: str
    provenance: Literal["reproduced", "imported_historical", "proposed"]
    notes: str = ""


class BaselineDossier(StrictModel):
    planVersion: str = PLAN_VERSION
    selectedCommit: str
    protocolVersion: str = PROTOCOL_VERSION
    declaredCameraProfile: str
    declaredWorkflow: str
    modelHashes: dict[str, str] = Field(default_factory=dict)
    dependencyManifests: list[str] = Field(default_factory=list)
    testReceipt: str | None = None
    inputIdentities: list[DossierAsset] = Field(default_factory=list)
    unresolvedGates: list[str] = Field(default_factory=list)
    permittedNextActions: list[str] = Field(default_factory=list)
    forbiddenActions: list[str] = Field(default_factory=list)
    capabilities: list[CapabilityEntry] = Field(default_factory=list)
    evidenceClasses: dict[str, str] = Field(default_factory=dict)


def default_capabilities() -> list[CapabilityEntry]:
    return [
        CapabilityEntry(
            id="manual_review",
            label="Manual review",
            status="usable",
            evidenceClass="software_verification",
            evidenceLink="docs/status/current.md",
            notes="Upload, tagging, playlist and template export work without language-model endpoints.",
        ),
        CapabilityEntry(
            id="team_level_tactical_estimates",
            label="Team-level tactical estimates",
            status="review_only",
            evidenceClass="independent_accuracy",
            evidenceLink="docs/status/current.md",
            notes="Team mapping awaits a declared human home/away choice. Automatic totals stay review-only.",
        ),
        CapabilityEntry(
            id="event_suggestions",
            label="Event suggestions",
            status="experimental",
            evidenceClass="independent_accuracy",
            evidenceLink="docs/status/current.md",
            notes="Provisional events exist; independent event AP is unproven.",
        ),
        CapabilityEntry(
            id="player_attribution",
            label="Player attribution",
            status="unproven",
            evidenceClass="independent_accuracy",
            evidenceLink="docs/status/current.md",
            notes="Identity continuity is not independently scored. Player totals remain withheld.",
        ),
        CapabilityEntry(
            id="physical_metrics",
            label="Physical metrics",
            status="unavailable",
            evidenceClass="independent_accuracy",
            evidenceLink="docs/status/current.md",
            notes="Distance/sprint totals are withheld until identity continuity and calibration gates pass.",
        ),
        CapabilityEntry(
            id="incident_review",
            label="Incident review",
            status="review_only",
            evidenceClass="analyst_acceptance",
            evidenceLink="docs/status/current.md",
            notes="Manual incident tagging is available. Automatic offside/foul rulings are excluded.",
        ),
    ]


def build_baseline_dossier(*, selected_commit: str | None = None) -> BaselineDossier:
    commit = selected_commit or _git_head() or INSPECTED_SOURCE_SHA
    capabilities = default_capabilities()
    missing = [entry.id for entry in capabilities if entry.id not in CAPABILITY_IDS]
    if missing:
        raise RuntimeError(f"capability ids drifted: {missing}")
    return BaselineDossier(
        selectedCommit=commit,
        declaredCameraProfile=INITIAL_CAMERA_PROFILE,
        declaredWorkflow=INITIAL_WORKFLOW,
        modelHashes={},
        dependencyManifests=[
            "backend/requirements-runtime.txt",
            "backend/requirements-ml.txt",
            "backend/release/",
        ],
        testReceipt=None,
        inputIdentities=[],
        unresolvedGates=[
            "independent_labels_0_of_18",
            "no_declared_camera_analyst_acceptance",
            "no_acceptance_qualified_hota_idf1",
            "no_current_source_sealed_inference",
            "g_network_required_before_non_loopback",
        ],
        permittedNextActions=[
            "Implement evidence/availability contracts and review UI.",
            "Instrument sampling counters on fixtures without a new cloud run.",
            "Complete independent annotation/declaration plan under frozen protocol v3.",
        ],
        forbiddenActions=[
            "Launch a new Daytona or GPU provider job without source-bound approval.",
            "Convert historical G-CAPACITY or G-PRODUCT success into current-source acceptance.",
            "Relax frozen evaluation protocol v3 or unlock labels from this workbench.",
            "Treat export fps as inference fps.",
            "Enable custom Rust/C++ without GA-18 approval.",
        ],
        capabilities=capabilities,
        evidenceClasses={
            "software_verification": "Local provider-disabled gates exist for a recorded release source; this workbench does not rerun them.",
            "pipeline_execution": "Earlier-source sealed CPU/GPU runs exist; current inspected SHA is not proven by those runs.",
            "independent_accuracy": "No acceptance-qualified tracking, ball, pitch, possession or event score.",
            "capacity": "Historical two-half times are diagnostics, not current billing.",
            "analyst_acceptance": "No declared-camera pilot has been accepted by the intended analyst.",
        },
    )


def http_dossier(*, repo_root: Path | None = None) -> dict[str, Any]:
    from .contracts import jsonable
    from .evaluation import current_repository_evaluation_gate
    from .native import native_gate, probe_gpu

    dossier = build_baseline_dossier()
    root = repo_root or Path(__file__).resolve().parents[3]
    return {
        "baseline": jsonable(dossier),
        "release": build_release_dossier(dossier),
        "evaluation": jsonable(current_repository_evaluation_gate()),
        "gpu": jsonable(probe_gpu()),
        "native": jsonable(native_gate(repo_root=root)),
        "capabilities": [jsonable(entry) for entry in dossier.capabilities],
    }


def build_release_dossier(baseline: BaselineDossier, *, loopback_only: bool = True) -> dict[str, Any]:
    return {
        "planVersion": baseline.planVersion,
        "selectedCommit": baseline.selectedCommit,
        "deploymentBoundary": "loopback" if loopback_only else "hosted_requires_g_network",
        "gNetworkRequiredForNonLocal": True,
        "authenticationNote": "Origin/Host checks and CORS are browser boundaries, not authentication.",
        "capabilities": [entry.model_dump(mode="json") for entry in baseline.capabilities],
        "unresolvedGates": list(baseline.unresolvedGates),
        "rightsReview": {
            "matchRecording": "required_before_share",
            "modelLicences": "review_ultralytics_and_exact_weights",
            "cloudInference": "host_credentials_never_in_worker",
            "youthFootage": "safeguarding_and_club_permission_required",
        },
        "restoreRunbook": "docs/runbooks/artifact-restore.md",
        "incidentPath": "docs/status/current.md",
        "nativeCode": "gated_inert",
        "rollback": "Revert the active manifest/feature flag; preserve existing artifacts; report stale outputs.",
    }


def _git_head() -> str | None:
    head = Path("/workspace/.git/HEAD")
    if not head.exists():
        return None
    text = head.read_text(encoding="utf-8").strip()
    if text.startswith("ref:"):
        ref = Path("/workspace/.git") / text.split(" ", 1)[1]
        if ref.exists():
            return ref.read_text(encoding="utf-8").strip()
        return None
    return text
