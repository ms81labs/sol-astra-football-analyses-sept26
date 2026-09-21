"""Leftover contract GET handlers, isolated from the production /api surface."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse

from ..storage import Storage
from .leftover_http import leftover_http_enabled

from .leftover_support import (
    EXTERNAL_BENCHMARK_DECISION_SURFACE_DIR,
    EXTERNAL_BENCHMARK_UI_BINDING_DIR,
    EXTERNAL_SOCCERNET_UI_BINDING_DIR,
    EXTERNAL_SOCCERTRACK_MATCH_BUNDLE_BRIDGE_DIR,
    EXTERNAL_SOCCERTRACK_UI_BINDING_DIR,
    VIDEO_TO_ANALYSIS_ACCEPTANCE_REPORT_BINDING_DIR,
    VIDEO_TO_ANALYSIS_BOUNDED_NEXT_SAMPLE_REPORT_BINDING_DIR,
    VIDEO_TO_ANALYSIS_DETECTOR_EVALUATION_REPORT_BINDING_DIR,
    VIDEO_TO_ANALYSIS_FINISH_LINE_PRODUCT_BINDING_DIR,
    VIDEO_TO_ANALYSIS_OPERATOR_DASHBOARD_BINDING_DIR,
    VIDEO_TO_ANALYSIS_OPERATOR_HANDOFF_BINDING_DIR,
    VIDEO_TO_ANALYSIS_POST_RELEASE_MONITORING_BINDING_DIR,
    VIDEO_TO_ANALYSIS_PROMOTED_RUNTIME_MONITORING_BINDING_DIR,
    VIDEO_TO_ANALYSIS_PROMOTION_REVIEW_REPORT_BINDING_DIR,
    VIDEO_TO_ANALYSIS_REAL_VIDEO_SCALEOUT_REPORT_BINDING_DIR,
    VIDEO_TO_ANALYSIS_RELEASE_READOUT_BINDING_DIR,
    _challenger_adapters_view,
    _decoder_challengers_view,
    _four_rates_view,
    _legacy_geometry,
    _legacy_geometry_profile,
    _production_decode_frames,
    _stale_permissions_view,
    _unmeasured_landmark_preview,
    _unpromoted_receipt,
)
from .access import (
    access_deletion_procedure,
    constrained_decoder,
    deployment_encryption,
    least_privilege_storage,
    protocol_network_allowlist,
    public_exposure_gate,
    signed_scoped_object_access,
    untrusted_model_output,
)
from .admission import (
    admit_camera,
)
from .adoption import (
    dependency_register,
)
from .artifacts import (
    columnar_observation_store,
    cross_tenant_cache_reuse,
    object_storage_adapter,
    secrets_in_artifacts,
)
from .assistance import (
    dual_budgets,
    embeddings_retrieve,
    escalation_requires_quality_gap,
    network_failure_preserves_unknown,
    preemptible_allowed,
    providers_disabled_fallback,
)
from .benchmarks import (
    experiment_receipt,
)
from .contracts import (
    unknown_metric,
)
from .costs import (
    credit_allocation,
    decimal_gb_to_gib,
    historical_capacity_seconds,
    scale_scenario,
)
from .decisions import (
    architecture_decisions,
)
from .dossier import (
    build_baseline_dossier,
    build_release_dossier,
)
from .evaluation import (
    analyst_workflow_measures,
    current_repository_evaluation_gate,
    evaluate_protocol_prerequisites,
    evaluation_measures,
    score_hota_idf1,
)
from .events import (
    learned_temporal,
)
from .evidence import (
    DEFINITION_VERSION,
    round_trip_unknown,
)
from .executables import (
    resolve_trusted_executable,
)
from .flags import (
    feature_enabled,
    shadow_metric,
)
from .geometry import (
    evaluate_landmarks,
    ground_contact_point,
)
from .identity import (
    appearance_embedding_policy,
    candidate_rejoin,
    cluster_mapping,
    cross_season_identity,
    face_recognition,
    reconnect_across_cut,
)
from .incidents import (
    broadcast_replay_not_simultaneous,
    elevated_body_part_homography,
    invisible_entity_not_repaired_by_larger_model,
    level0_incident_package,
    level1_positional_aid,
    level2_schematic_replay,
    level3_multiview,
    vlm_confidence_is_not_referee,
)
from .jobs import (
    deployment_mode,
    distributed_broker,
    egress_policy,
    signed_scoped_job_access,
    vector_database,
)
from .media import (
    decode_memory_policy,
    vid_stride_policy,
)
from .milestones import (
    milestone_plan,
    owners,
    progress_signal,
)
from .native import (
    cuda_visibility_is_not_video_capability,
    custom_native_justification,
    ffmpeg_build_review,
    native_gate,
    no_rpc_fleet,
    pinned_native_artifacts,
    probe_gpu,
    qualified_os_profiles,
    quantized_weight_memory,
)
from .privacy import (
    dpia_screen,
    residency_claim,
)
from .providers import (
    cloud_adapter,
    local_adapter,
    provider_roster,
)
from .quantities import (
    heatmap_availability,
    pitch_axes,
    split_scores,
    transform_legacy_display,
)
from .recovery import (
    full_disk,
    recovery_objectives,
    support_bundle,
    unresolved_incidents,
)
from .reports import (
    held_out_questions,
)
from .repository import (
    http_may_run_gpu,
    RepositoryAdapter,
    vector_broker_required,
)
from .research import (
    research_lane,
)
from .review import (
    collaboration_lock,
)
from .rights import (
    dataset_manifest,
    incident_response,
    licence_register,
    rights_register,
)
from .risks import (
    independent_reviewer,
    risk_register,
    telestration_before_3d,
    worked_match_flow,
)
from .roster import (
    frontier_provider_role,
    label_products,
    model_roster,
    promotion_gate,
    video_model_roster,
)
from .shot_model import (
    tree_challenger,
)
from .targets import (
    metadata_api_targets,
)
from .timing import (
    gpu_timing_scope,
    stage_timing,
)
from .training import (
    data_pools,
    drill_library,
    sampling_policy,
)
from .xt import (
    xt_deferred_plan,
)

def create_leftover_get_router(storage: Storage) -> APIRouter:
    json_router, _html_router = create_leftover_get_routers(storage)
    return json_router


def create_leftover_get_routers(storage: Storage) -> tuple[APIRouter, APIRouter]:
    def _external_soccernet_ui_binding_root() -> Path:
        return storage.storage_root / EXTERNAL_SOCCERNET_UI_BINDING_DIR

    def _load_external_soccernet_view_model() -> dict:
        view_model_path = _external_soccernet_ui_binding_root() / "analysis_product_ui_view_model.json"
        if not view_model_path.exists():
            raise HTTPException(status_code=404, detail="SoccerNet analysis product UI binding not ready")
        return json.loads(view_model_path.read_text(encoding="utf-8"))

    def _external_soccertrack_match_bundle_bridge_root() -> Path:
        return storage.storage_root / EXTERNAL_SOCCERTRACK_MATCH_BUNDLE_BRIDGE_DIR

    def _load_external_soccertrack_match_bundle(match_id: str) -> dict:
        bundle_path = _external_soccertrack_match_bundle_bridge_root() / "soccertrack_external_match_bundle.json"
        if not bundle_path.exists():
            raise HTTPException(status_code=404, detail="SoccerTrack external match bundle bridge not ready")
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        expected_match_ids = {match_id, f"soccertrack:{match_id}"}
        bundle_match = bundle.get("match") if isinstance(bundle.get("match"), dict) else {}
        provenance = bundle.get("provenance") if isinstance(bundle.get("provenance"), dict) else {}
        actual_match_ids = {
            str(bundle_match.get("id") or ""),
            str(provenance.get("externalSourceMatchId") or ""),
        }
        if not expected_match_ids.intersection(actual_match_ids):
            raise HTTPException(status_code=404, detail="SoccerTrack external match bundle not found")
        if bundle.get("schemaVersion") != "match_bundle_v1":
            raise HTTPException(status_code=409, detail="SoccerTrack external match bundle contract invalid")
        return bundle

    def _external_soccertrack_ui_binding_root() -> Path:
        return storage.storage_root / EXTERNAL_SOCCERTRACK_UI_BINDING_DIR

    def _external_benchmark_ui_binding_root() -> Path:
        return storage.storage_root / EXTERNAL_BENCHMARK_UI_BINDING_DIR

    def _external_benchmark_decision_surface_root() -> Path:
        return storage.storage_root / EXTERNAL_BENCHMARK_DECISION_SURFACE_DIR

    def _video_to_analysis_finish_line_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_FINISH_LINE_PRODUCT_BINDING_DIR

    def _video_to_analysis_acceptance_report_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_ACCEPTANCE_REPORT_BINDING_DIR

    def _video_to_analysis_operator_handoff_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_OPERATOR_HANDOFF_BINDING_DIR

    def _video_to_analysis_release_readout_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_RELEASE_READOUT_BINDING_DIR

    def _video_to_analysis_post_release_monitoring_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_POST_RELEASE_MONITORING_BINDING_DIR

    def _video_to_analysis_detector_evaluation_report_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_DETECTOR_EVALUATION_REPORT_BINDING_DIR

    def _video_to_analysis_promotion_review_report_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_PROMOTION_REVIEW_REPORT_BINDING_DIR

    def _video_to_analysis_promoted_runtime_monitoring_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_PROMOTED_RUNTIME_MONITORING_BINDING_DIR

    def _video_to_analysis_operator_dashboard_binding_root() -> Path:
        return storage.storage_root / VIDEO_TO_ANALYSIS_OPERATOR_DASHBOARD_BINDING_DIR

    def _video_to_analysis_real_video_scaleout_report_binding_root() -> Path:
        fixed_root = storage.storage_root / VIDEO_TO_ANALYSIS_REAL_VIDEO_SCALEOUT_REPORT_BINDING_DIR
        candidate_root = fixed_root.parent
        dirs = [
            path
            for path in candidate_root.glob("video_to_analysis_real_video_scaleout_report_route_binding_v*")
            if path.is_dir()
            and (path / "real_video_scaleout_report_view_model.json").exists()
            and (path / "real_video_scaleout_report_route_contract.json").exists()
        ]
        if not dirs:
            return fixed_root
        return max(dirs, key=lambda path: int(path.name.rsplit("_v", 1)[-1]))

    def _video_to_analysis_bounded_next_sample_report_binding_root() -> Path:
        fixed_root = storage.storage_root / VIDEO_TO_ANALYSIS_BOUNDED_NEXT_SAMPLE_REPORT_BINDING_DIR
        candidate_root = fixed_root.parent
        dirs = [
            path
            for path in candidate_root.glob("video_to_analysis_bounded_next_sample_report_route_binding_v*")
            if path.is_dir()
            and (path / "bounded_next_sample_report_view_model.json").exists()
            and (path / "bounded_next_sample_report_route_contract.json").exists()
        ]
        if not dirs:
            return fixed_root
        return max(dirs, key=lambda path: int(path.name.rsplit("_v", 1)[-1]))

    def _load_external_benchmark_view_model() -> dict:
        binding_root = _external_benchmark_ui_binding_root()
        view_model_path = binding_root / "external_benchmark_product_ui_view_model.json"
        contract_path = binding_root / "external_benchmark_product_ui_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="External benchmark product UI binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/external/benchmark/report":
            raise HTTPException(status_code=409, detail="External benchmark product UI route contract invalid")
        if route_contract.get("htmlRoutePath") != "/external/benchmark/report":
            raise HTTPException(status_code=409, detail="External benchmark product UI route contract invalid")
        if view_model.get("schemaVersion") != "football_external_benchmark_product_ui_view_model_v1":
            raise HTTPException(status_code=409, detail="External benchmark product UI binding contract invalid")
        return view_model

    def _load_external_benchmark_report_html() -> str:
        _load_external_benchmark_view_model()
        html_path = _external_benchmark_ui_binding_root() / "external_benchmark_product_ui_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="External benchmark product UI binding not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_external_benchmark_decision_view_model() -> dict:
        surface_root = _external_benchmark_decision_surface_root()
        view_model_path = surface_root / "product_decision_surface_view_model.json"
        contract_path = surface_root / "product_decision_surface_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="External benchmark decision surface not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/external/benchmark/decision":
            raise HTTPException(status_code=409, detail="External benchmark decision surface route contract invalid")
        if route_contract.get("htmlRoutePath") != "/external/benchmark/decision":
            raise HTTPException(status_code=409, detail="External benchmark decision surface route contract invalid")
        if view_model.get("schemaVersion") != "external_benchmark_product_decision_surface_view_model_v1":
            raise HTTPException(status_code=409, detail="External benchmark decision surface contract invalid")
        return view_model

    def _load_external_benchmark_decision_html() -> str:
        _load_external_benchmark_decision_view_model()
        html_path = _external_benchmark_decision_surface_root() / "product_decision_surface_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="External benchmark decision surface not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_finish_line_view_model() -> dict:
        binding_root = _video_to_analysis_finish_line_binding_root()
        view_model_path = binding_root / "finish_line_product_view_model.json"
        contract_path = binding_root / "finish_line_product_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis finish-line binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/finish-line":
            raise HTTPException(status_code=409, detail="Video-to-analysis finish-line route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/finish-line":
            raise HTTPException(status_code=409, detail="Video-to-analysis finish-line route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_finish_line_product_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis finish-line binding contract invalid")
        return view_model

    def _load_video_to_analysis_finish_line_html() -> str:
        _load_video_to_analysis_finish_line_view_model()
        html_path = _video_to_analysis_finish_line_binding_root() / "finish_line_product_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis finish-line HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_acceptance_report_view_model() -> dict:
        binding_root = _video_to_analysis_acceptance_report_binding_root()
        view_model_path = binding_root / "acceptance_report_view_model.json"
        contract_path = binding_root / "acceptance_report_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis acceptance report binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/acceptance-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis acceptance report route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/acceptance-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis acceptance report route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_acceptance_report_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis acceptance report binding contract invalid")
        return view_model

    def _load_video_to_analysis_acceptance_report_html() -> str:
        _load_video_to_analysis_acceptance_report_view_model()
        html_path = _video_to_analysis_acceptance_report_binding_root() / "acceptance_report_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis acceptance report HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_operator_handoff_view_model() -> dict:
        binding_root = _video_to_analysis_operator_handoff_binding_root()
        view_model_path = binding_root / "operator_handoff_view_model.json"
        contract_path = binding_root / "operator_handoff_bound_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis operator handoff binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/operator-handoff":
            raise HTTPException(status_code=409, detail="Video-to-analysis operator handoff route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/operator-handoff":
            raise HTTPException(status_code=409, detail="Video-to-analysis operator handoff route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_operator_handoff_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis operator handoff binding contract invalid")
        return view_model

    def _load_video_to_analysis_operator_handoff_html() -> str:
        _load_video_to_analysis_operator_handoff_view_model()
        html_path = _video_to_analysis_operator_handoff_binding_root() / "operator_handoff_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis operator handoff HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_release_readout_view_model() -> dict:
        binding_root = _video_to_analysis_release_readout_binding_root()
        view_model_path = binding_root / "release_readout_view_model.json"
        contract_path = binding_root / "release_readout_bound_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis release readout binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/release-readout":
            raise HTTPException(status_code=409, detail="Video-to-analysis release readout route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/release-readout":
            raise HTTPException(status_code=409, detail="Video-to-analysis release readout route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_release_readout_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis release readout binding contract invalid")
        return view_model

    def _load_video_to_analysis_release_readout_html() -> str:
        _load_video_to_analysis_release_readout_view_model()
        html_path = _video_to_analysis_release_readout_binding_root() / "release_readout_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis release readout HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_post_release_monitoring_view_model() -> dict:
        binding_root = _video_to_analysis_post_release_monitoring_binding_root()
        view_model_path = binding_root / "post_release_monitoring_view_model.json"
        contract_path = binding_root / "post_release_monitoring_bound_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis post-release monitoring binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/post-release-monitoring":
            raise HTTPException(status_code=409, detail="Video-to-analysis post-release monitoring route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/post-release-monitoring":
            raise HTTPException(status_code=409, detail="Video-to-analysis post-release monitoring route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_post_release_monitoring_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis post-release monitoring binding contract invalid")
        return view_model

    def _load_video_to_analysis_post_release_monitoring_html() -> str:
        _load_video_to_analysis_post_release_monitoring_view_model()
        html_path = _video_to_analysis_post_release_monitoring_binding_root() / "post_release_monitoring_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis post-release monitoring HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_detector_evaluation_report_view_model() -> dict:
        binding_root = _video_to_analysis_detector_evaluation_report_binding_root()
        view_model_path = binding_root / "detector_evaluation_report_view_model.json"
        contract_path = binding_root / "detector_evaluation_report_bound_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis detector evaluation report binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/detector-evaluation-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis detector evaluation report route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/detector-evaluation-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis detector evaluation report route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_detector_evaluation_report_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis detector evaluation report binding contract invalid")
        return view_model

    def _load_video_to_analysis_detector_evaluation_report_html() -> str:
        _load_video_to_analysis_detector_evaluation_report_view_model()
        html_path = _video_to_analysis_detector_evaluation_report_binding_root() / "detector_evaluation_report_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis detector evaluation report HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_promotion_review_report_view_model() -> dict:
        binding_root = _video_to_analysis_promotion_review_report_binding_root()
        view_model_path = binding_root / "promotion_review_report_view_model.json"
        contract_path = binding_root / "promotion_review_report_bound_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis promotion review report binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/promotion-review":
            raise HTTPException(status_code=409, detail="Video-to-analysis promotion review route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/promotion-review":
            raise HTTPException(status_code=409, detail="Video-to-analysis promotion review route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_promotion_review_report_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis promotion review binding contract invalid")
        return view_model

    def _load_video_to_analysis_promotion_review_report_html() -> str:
        _load_video_to_analysis_promotion_review_report_view_model()
        html_path = _video_to_analysis_promotion_review_report_binding_root() / "promotion_review_report_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis promotion review HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_promoted_runtime_monitoring_view_model() -> dict:
        binding_root = _video_to_analysis_promoted_runtime_monitoring_binding_root()
        view_model_path = binding_root / "promoted_runtime_monitoring_view_model.json"
        contract_path = binding_root / "promoted_runtime_monitoring_bound_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis promoted runtime monitoring binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/promoted-runtime-monitoring":
            raise HTTPException(status_code=409, detail="Video-to-analysis promoted runtime monitoring route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/promoted-runtime-monitoring":
            raise HTTPException(status_code=409, detail="Video-to-analysis promoted runtime monitoring route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_promoted_runtime_monitoring_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis promoted runtime monitoring binding contract invalid")
        return view_model

    def _load_video_to_analysis_promoted_runtime_monitoring_html() -> str:
        _load_video_to_analysis_promoted_runtime_monitoring_view_model()
        html_path = _video_to_analysis_promoted_runtime_monitoring_binding_root() / "promoted_runtime_monitoring_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis promoted runtime monitoring HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_operator_dashboard_view_model() -> dict:
        binding_root = _video_to_analysis_operator_dashboard_binding_root()
        view_model_path = binding_root / "operator_dashboard_view_model.json"
        contract_path = binding_root / "operator_dashboard_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis operator dashboard binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/operator-dashboard":
            raise HTTPException(status_code=409, detail="Video-to-analysis operator dashboard route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/operator-dashboard":
            raise HTTPException(status_code=409, detail="Video-to-analysis operator dashboard route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_operator_dashboard_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis operator dashboard binding contract invalid")
        return view_model

    def _load_video_to_analysis_operator_dashboard_html() -> str:
        _load_video_to_analysis_operator_dashboard_view_model()
        html_path = _video_to_analysis_operator_dashboard_binding_root() / "operator_dashboard_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis operator dashboard HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_real_video_scaleout_report_view_model() -> dict:
        binding_root = _video_to_analysis_real_video_scaleout_report_binding_root()
        view_model_path = binding_root / "real_video_scaleout_report_view_model.json"
        contract_path = binding_root / "real_video_scaleout_report_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis real-video scaleout report binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/real-video-scaleout-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis real-video scaleout report route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/real-video-scaleout-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis real-video scaleout report route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_real_video_scaleout_report_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis real-video scaleout report binding contract invalid")
        return view_model

    def _load_video_to_analysis_real_video_scaleout_report_html() -> str:
        _load_video_to_analysis_real_video_scaleout_report_view_model()
        html_path = _video_to_analysis_real_video_scaleout_report_binding_root() / "real_video_scaleout_report_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis real-video scaleout report HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_video_to_analysis_bounded_next_sample_report_view_model() -> dict:
        binding_root = _video_to_analysis_bounded_next_sample_report_binding_root()
        view_model_path = binding_root / "bounded_next_sample_report_view_model.json"
        contract_path = binding_root / "bounded_next_sample_report_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis bounded next-sample report binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if route_contract.get("apiRoutePath") != "/api/video-to-analysis/bounded-next-sample-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis bounded next-sample report route contract invalid")
        if route_contract.get("htmlRoutePath") != "/video-to-analysis/bounded-next-sample-report":
            raise HTTPException(status_code=409, detail="Video-to-analysis bounded next-sample report route contract invalid")
        if view_model.get("schemaVersion") != "video_to_analysis_bounded_next_sample_report_view_model_v1":
            raise HTTPException(status_code=409, detail="Video-to-analysis bounded next-sample report binding contract invalid")
        return view_model

    def _load_video_to_analysis_bounded_next_sample_report_html() -> str:
        _load_video_to_analysis_bounded_next_sample_report_view_model()
        html_path = _video_to_analysis_bounded_next_sample_report_binding_root() / "bounded_next_sample_report_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Video-to-analysis bounded next-sample report HTML not ready")
        return html_path.read_text(encoding="utf-8")

    def _load_external_soccertrack_view_model(match_id: str) -> dict:
        binding_root = _external_soccertrack_ui_binding_root()
        view_model_path = binding_root / "analysis_product_ui_view_model.json"
        contract_path = binding_root / "analysis_product_ui_route_contract.json"
        if not view_model_path.exists() or not contract_path.exists():
            raise HTTPException(status_code=404, detail="SoccerTrack analysis product UI binding not ready")
        view_model = json.loads(view_model_path.read_text(encoding="utf-8"))
        route_contract = json.loads(contract_path.read_text(encoding="utf-8"))
        allowed_paths = {
            route_contract.get("apiRoutePath"),
            route_contract.get("routePath"),
        }
        expected_paths = {
            f"/api/external/soccertrack/{match_id}/analysis",
            f"/external/soccertrack/{match_id}/analysis",
        }
        if not allowed_paths.intersection(expected_paths):
            raise HTTPException(status_code=404, detail="SoccerTrack analysis product UI binding not found")
        if view_model.get("schemaVersion") != "soccertrack_analysis_product_ui_view_model_v1":
            raise HTTPException(status_code=409, detail="SoccerTrack analysis product UI binding contract invalid")
        return view_model

    def _load_external_soccertrack_analysis_html(match_id: str) -> str:
        _load_external_soccertrack_view_model(match_id)
        html_path = _external_soccertrack_ui_binding_root() / "analysis_product_ui_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="SoccerTrack analysis product UI binding not ready")
        return html_path.read_text(encoding="utf-8")

    def _support_bundle_view() -> dict:
        payload = support_bundle(consented=False, ttl_seconds=0.0, now=0.0)
        return {key: value for key, value in payload.items() if key != "expired"}

    router = APIRouter()
    html_router = APIRouter()

    @router.get("/external/soccernet/full-analysis")
    def get_external_soccernet_full_analysis() -> dict:
        return _load_external_soccernet_view_model()

    @router.get("/external/soccertrack/{match_id}/export/match.json")
    def export_external_soccertrack_match_json(match_id: str) -> dict:
        return _load_external_soccertrack_match_bundle(match_id)

    @router.get("/external/soccertrack/{match_id}/analysis")
    def get_external_soccertrack_analysis(match_id: str) -> dict:
        return _load_external_soccertrack_view_model(match_id)

    @router.get("/external/benchmark/report")
    def get_external_benchmark_report() -> dict:
        return _load_external_benchmark_view_model()

    @router.get("/external/benchmark/decision")
    def get_external_benchmark_decision_surface() -> dict:
        return _load_external_benchmark_decision_view_model()

    @router.get("/video-to-analysis/finish-line")
    def get_video_to_analysis_finish_line() -> dict:
        return _load_video_to_analysis_finish_line_view_model()

    @router.get("/video-to-analysis/acceptance-report")
    def get_video_to_analysis_acceptance_report() -> dict:
        return _load_video_to_analysis_acceptance_report_view_model()

    @router.get("/video-to-analysis/operator-handoff")
    def get_video_to_analysis_operator_handoff() -> dict:
        return _load_video_to_analysis_operator_handoff_view_model()

    @router.get("/video-to-analysis/release-readout")
    def get_video_to_analysis_release_readout() -> dict:
        return _load_video_to_analysis_release_readout_view_model()

    @router.get("/video-to-analysis/post-release-monitoring")
    def get_video_to_analysis_post_release_monitoring() -> dict:
        return _load_video_to_analysis_post_release_monitoring_view_model()

    @router.get("/video-to-analysis/detector-evaluation-report")
    def get_video_to_analysis_detector_evaluation_report() -> dict:
        return _load_video_to_analysis_detector_evaluation_report_view_model()

    @router.get("/video-to-analysis/promotion-review")
    def get_video_to_analysis_promotion_review_report() -> dict:
        return _load_video_to_analysis_promotion_review_report_view_model()

    @router.get("/video-to-analysis/promoted-runtime-monitoring")
    def get_video_to_analysis_promoted_runtime_monitoring() -> dict:
        return _load_video_to_analysis_promoted_runtime_monitoring_view_model()

    @router.get("/video-to-analysis/operator-dashboard")
    def get_video_to_analysis_operator_dashboard() -> dict:
        return _load_video_to_analysis_operator_dashboard_view_model()

    @router.get("/video-to-analysis/real-video-scaleout-report")
    def get_video_to_analysis_real_video_scaleout_report() -> dict:
        return _load_video_to_analysis_real_video_scaleout_report_view_model()

    @router.get("/video-to-analysis/bounded-next-sample-report")
    def get_video_to_analysis_bounded_next_sample_report() -> dict:
        return _load_video_to_analysis_bounded_next_sample_report_view_model()

    @router.get("/evaluation/measures")
    def get_evaluation_measures() -> dict:
        return evaluation_measures()

    @router.get("/evaluation/workflow")
    def get_evaluation_workflow() -> dict:
        return analyst_workflow_measures()

    @router.get("/evaluation/protocol")
    def get_evaluation_protocol() -> dict:
        return current_repository_evaluation_gate().model_dump(mode="json")

    @router.get("/evaluation/prerequisites")
    def get_evaluation_prerequisites() -> dict:
        return evaluate_protocol_prerequisites(
            complete_tasks=0,
            complete_minutes=0.0,
            locked_labels_present=False,
            native_predictions_present=False,
            team_declarations_present=False,
            scorer_replayable=True,
        ).model_dump(mode="json")

    @router.get("/research/lane")
    def get_research_lane() -> dict:
        return research_lane()

    @router.get("/xt")
    def get_xt() -> dict:
        return xt_deferred_plan()

    @router.get("/credits")
    def get_credits() -> dict:
        return credit_allocation()

    @router.get("/admission/{profile}")
    def get_admission(profile: str) -> dict:
        try:
            return admit_camera(profile).model_dump(mode="json")  # type: ignore[arg-type]
        except KeyError as exc:
            raise HTTPException(status_code=400, detail="Unknown camera profile") from exc

    @router.get("/training/drills")
    def get_training_drills() -> dict:
        return drill_library()

    @router.get("/rights")
    def get_rights() -> dict:
        return rights_register()

    @router.get("/rights/licences")
    def get_licence_register() -> dict:
        return licence_register()

    @router.get("/rights/datasets")
    def get_dataset_manifest() -> dict:
        return dataset_manifest()

    @router.get("/rights/incident")
    def get_incident_response() -> dict:
        return incident_response()

    @router.get("/providers")
    def get_providers() -> dict:
        return {
            "roster": provider_roster(),
            "local": local_adapter(enabled=False),
            "cloud": cloud_adapter(enabled=False),
        }

    @router.get("/dependencies")
    def get_dependencies() -> dict:
        return dependency_register()

    @router.get("/telestration")
    def get_telestration() -> dict:
        return telestration_before_3d()

    @router.get("/roster")
    def get_roster() -> dict:
        return {"items": model_roster()}

    @router.get("/roster/labels")
    def get_roster_labels() -> dict:
        return label_products()

    @router.get("/roster/video")
    def get_roster_video() -> dict:
        return video_model_roster()

    @router.get("/roster/frontier")
    def get_roster_frontier() -> dict:
        return frontier_provider_role(model_id="unspecified")

    @router.get("/roster/promotion/{task}")
    def get_roster_promotion(task: str) -> dict:
        return promotion_gate(task=task, independent_accepted=False, licence_recorded=False)

    @router.get("/risks")
    def get_risks() -> dict:
        return {"items": risk_register()}

    @router.get("/milestones")
    def get_milestones() -> dict:
        return {
            "items": milestone_plan(),
            "owners": owners(),
            "progress": progress_signal(
                completed_analyst_tasks=0,
                validated_capability_gates=0,
                merged_files=0,
            ),
        }

    @router.get("/targets")
    def get_targets() -> dict:
        return metadata_api_targets()

    @router.get("/decisions")
    def get_decisions() -> dict:
        return {"items": architecture_decisions()}

    @router.get("/residency")
    def get_residency() -> dict:
        return residency_claim(requested_region="eu", provider="daytona")

    @router.get("/broker")
    def get_broker() -> dict:
        return distributed_broker(measured_workload_needs=False)

    @router.get("/vector")
    def get_vector() -> dict:
        return vector_database(measured_recall_benefit=False)

    @router.get("/deployment/{mode}")
    def get_deployment_mode(mode: str) -> dict:
        try:
            return deployment_mode(mode)
        except KeyError as exc:
            raise HTTPException(status_code=400, detail="Unknown deployment mode") from exc

    @router.get("/recovery")
    def get_recovery() -> dict:
        return {
            "deletion": access_deletion_procedure(requested=False, controller_recorded=False),
            "unresolvedIncidents": unresolved_incidents(),
            "recoveryObjectives": recovery_objectives(data_volume_measured=False, disruption_measured=False),
            "stalePermissions": _stale_permissions_view(),
        }

    @router.get("/scale/{matches}")
    def get_scale_scenario(matches: int) -> dict:
        payload = dict(scale_scenario(matches_per_month=matches))
        payload["gbEqualsGiB"] = False
        payload["decimalGb"] = 5.4
        payload["gib"] = decimal_gb_to_gib(5.4)
        return payload

    @router.get("/privacy/dpia")
    def get_privacy_dpia() -> dict:
        return dpia_screen(
            youth_footage=False,
            identifiable_faces=True,
            cloud_requested=False,
            cloud_permitted=False,
        ).model_dump(mode="json")

    @router.get("/gpu")
    def get_gpu() -> dict:
        capability = probe_gpu()
        payload = capability.model_dump(mode="json")
        payload["canPromoteDefault"] = False
        payload["videoEngine"] = cuda_visibility_is_not_video_capability(cuda_visible=capability.available)
        return payload

    @router.get("/native")
    def get_native() -> dict:
        gate = native_gate(repo_root=Path.cwd(), approval_env=dict(os.environ))
        return {
            **gate.model_dump(mode="json"),
            "pinned": pinned_native_artifacts(),
            "osProfiles": qualified_os_profiles(profile="ubuntu"),
            "ffmpeg": ffmpeg_build_review(),
            "rpcFleet": no_rpc_fleet(),
            "customNative": custom_native_justification(measured_savings=False, required_capability=False),
        }

    @router.get("/security")
    def get_security(x_deployment_boundary: str | None = Header(default=None)) -> dict:
        bound = (x_deployment_boundary or "loopback").lower()
        return {
            "modelOutput": untrusted_model_output(
                claimed_actions=[],
                allowed_actions=frozenset({"open_interval", "draft_report"}),
                evidence_ids=[],
                known_ids=set(),
            ),
            "publicExposure": public_exposure_gate(security_review_accepted=False, bound=bound),
            "encryption": deployment_encryption(boundary=bound),
            "allowlist": protocol_network_allowlist(url="http://127.0.0.1/"),
            "decoder": constrained_decoder(
                argv=[str(_main.resolve_trusted_executable("ffmpeg")), "-i", "local.mp4"],
                network_enabled=False,
            ),
            "storage": least_privilege_storage(credential_scope="object"),
            "secretsAdmitted": secrets_in_artifacts("cleanupResult=unknown")["admitted"],
            "signedJobAccess": signed_scoped_job_access(token=None, job_id="job-1", token_job_id=None),
            "egress": egress_policy(destination="https://evil.example", authorised_hosts=frozenset()),
        }

    @router.get("/assistance")
    def get_assistance() -> dict:
        fallback = providers_disabled_fallback(metrics=[], events=[])
        return {
            **fallback,
            "providersEnabled": False,
            "budgets": dual_budgets(vision=2.0, language=0.1),
            "embeddings": embeddings_retrieve("", passages=[]),
            "escalation": escalation_requires_quality_gap(model_uncertain=True, measured_gap=False),
        }

    @router.get("/decode/memory")
    def get_decode_memory() -> dict:
        gpu = probe_gpu()
        return decode_memory_policy(
            mode="offline",
            hardware_decode_ok=False,
            cuda_visible=gpu.available,
            video_engine_capability=False,
        )

    @router.get("/reviewer")
    def get_reviewer() -> dict:
        return independent_reviewer(developer="unrecorded", reviewer="unrecorded", inspected_held_out=False)

    @router.get("/flow")
    def get_worked_flow() -> dict:
        return worked_match_flow()

    @router.get("/identity")
    def get_identity_policy() -> dict:
        payload = reconnect_across_cut(cut_detected=False)
        payload["appearance"] = appearance_embedding_policy()
        payload["faceRecognition"] = face_recognition(requested=False)
        payload["crossSeasonIdentity"] = cross_season_identity(requested=False)
        payload["candidateRejoin"] = candidate_rejoin()
        return payload

    @router.get("/incidents/ladder")
    def get_incident_ladder() -> dict:
        return {
            "level0": level0_incident_package(clips=[], notes=[], bookmarks=[]),
            "level1": level1_positional_aid(
                touch_interval=(0.0, 0.12),
                attacker_x=0.0,
                offside_line_x=0.0,
                uncertainty_m=3.0,
            ),
            "level2": level2_schematic_replay(coordinates=[]),
            "level3": level3_multiview(),
            "vlm": vlm_confidence_is_not_referee(confidence=0.99),
            "replay": broadcast_replay_not_simultaneous(same_timestamp=False),
            "homography": elevated_body_part_homography(part="foot"),
            "invisible": invisible_entity_not_repaired_by_larger_model(visible=False),
        }

    @router.get("/evaluation/hota")
    def get_evaluation_hota() -> dict:
        return score_hota_idf1(
            label_space="official_pitch",
            hand_edited_summary=False,
            native_predictions_present=False,
        )

    @router.get("/shots/tree")
    def get_shot_tree() -> dict:
        return {
            "tree": tree_challenger(logistic_calibrated=False),
            "temporal": learned_temporal(labelled_errors_justify=False),
        }

    @router.get("/collaboration")
    def get_collaboration() -> dict:
        return {
            "local": collaboration_lock(mode="local_only"),
            "hosted": collaboration_lock(mode="hosted_collaboration", lock_holder="analyst-a", requester="analyst-b"),
        }

    @router.get("/media/stride")
    def get_media_stride() -> dict:
        return vid_stride_policy()

    @router.get("/cache/tenancy")
    def get_cache_tenancy() -> dict:
        return {
            "crossTenant": cross_tenant_cache_reuse(
                source_tenant="loopback",
                requester_tenant="other",
                explicit_privacy_design=False,
            ),
            "columnar": columnar_observation_store(),
        }

    @router.get("/quantities/axes")
    def get_pitch_axes() -> dict:
        return pitch_axes()

    @router.get("/timing/gpu")
    def get_gpu_timing() -> dict:
        return gpu_timing_scope(submission_ms=0.0, completed_ms=None, device_aware=False)

    @router.get("/native/memory")
    def get_native_memory() -> dict:
        return quantized_weight_memory(weight_bytes=0)

    @router.get("/capacity")
    def get_capacity() -> dict:
        return historical_capacity_seconds()

    @router.get("/repository")
    def get_repository() -> dict:
        return {
            "httpMayRunGpu": http_may_run_gpu(),
            "vectorBrokerRequired": vector_broker_required(),
            "replacesStorageModule": RepositoryAdapter.replaces_storage_module,
            "backendName": RepositoryAdapter.backend_name,
        }

    @router.get("/support/bundle")
    def get_support_bundle() -> dict:
        return _support_bundle_view()

    @router.get("/geometry/contact")
    def get_geometry_contact() -> dict:
        return ground_contact_point((0.0, 0.0, 10.0, 20.0))

    @router.get("/geometry/legacy")
    def get_geometry_legacy() -> dict:
        return _legacy_geometry()

    @router.get("/geometry/landmarks")
    def get_geometry_landmarks() -> dict:
        return evaluate_landmarks(_legacy_geometry_profile(), max_p95_m=3.0)

    @router.get("/geometry/preview")
    def get_geometry_preview() -> dict:
        return _unmeasured_landmark_preview()

    @router.get("/metrics/network-failure")
    def get_network_failure() -> dict:
        return network_failure_preserves_unknown(metric_value=None, generated_number=0.0)

    @router.get("/reports/held-out")
    def get_held_out_questions() -> dict:
        return {"questions": held_out_questions()}

    @router.get("/storage/object")
    def get_object_storage() -> dict:
        return object_storage_adapter(hosted_approved=False)

    @router.get("/recovery/disk")
    def get_recovery_disk() -> dict:
        return full_disk()

    @router.get("/recovery/restore")
    def get_recovery_restore() -> dict:
        return storage.restore_exercise_run()

    @router.get("/preemptible")
    def get_preemptible() -> dict:
        return {"allowed": preemptible_allowed(checkpoints=False, restart_semantics=False)}

    @router.get("/experiments/{experiment}")
    def get_experiment(experiment: str) -> dict:
        return experiment_receipt(experiment, hardware_verified=False, bottleneck_documented=False).model_dump(mode="json")

    @router.get("/timing/stages")
    def get_stage_timing() -> dict:
        return stage_timing(
            decode=1.0,
            preprocess=1.0,
            transfer=1.0,
            inference=1.0,
            association=1.0,
            recovery=1.0,
            serialisation=1.0,
            wall_time=3.0,
            overlapped=True,
        ).model_dump(mode="json")

    @router.get("/identity/clusters/{cluster_id}")
    def get_identity_cluster(cluster_id: int) -> dict:
        return cluster_mapping(cluster_id=cluster_id, selected_semantic=None).model_dump(mode="json")

    @router.get("/training/pools")
    def get_training_pools() -> dict:
        return {"pools": list(data_pools())}

    @router.get("/flags/shadow/{name}")
    def get_shadow_metric(name: str) -> dict:
        return shadow_metric(name)

    @router.get("/flags/{name}/enabled")
    def get_feature_enabled(name: str) -> dict:
        return {"name": name, "enabled": feature_enabled(name, env={})}

    @router.get("/quantities/display")
    def get_legacy_display() -> dict:
        return transform_legacy_display(x=0.0, y=0.0, from_display=True)

    @router.get("/metrics/round-trip")
    def get_metric_round_trip() -> dict:
        restored = round_trip_unknown(
            unknown_metric("possession_pct", definition_version=DEFINITION_VERSION, reason_codes=["ZERO_DENOMINATOR"])
        )
        dumped = restored.model_dump(mode="json")
        dumped["publishedValue"] = restored.published_value()
        return dumped

    @router.get("/decode/frames")
    def get_decode_frames() -> dict:
        return _production_decode_frames(storage.storage_root)

    @router.get("/decode/challengers")
    def get_decode_challengers() -> dict:
        return _decoder_challengers_view(storage.storage_root)

    @router.get("/challengers")
    def get_challengers() -> dict:
        return _challenger_adapters_view()

    @router.get("/permissions/stale")
    def get_stale_permissions() -> dict:
        return _stale_permissions_view()

    @router.get("/heatmap")
    def get_heatmap() -> dict:
        return heatmap_availability(identity_continuous=False)

    @router.get("/dossier/release")
    def get_release_dossier() -> dict:
        return build_release_dossier(build_baseline_dossier(), loopback_only=True)

    @router.get("/rates/four")
    def get_four_rates() -> dict:
        return _four_rates_view()

    @router.get("/receipts/promotion")
    def get_promotion_receipt() -> dict:
        return _unpromoted_receipt()

    @router.get("/quantities/scores")
    def get_split_scores() -> dict:
        return split_scores(detector_score=None, calibrated_probability=None, interval=None)

    @router.get("/access/signed")
    def get_signed_object_access() -> dict:
        return signed_scoped_object_access(token=None, object_id="", token_object_id=None)

    @router.get("/training/sampling")
    def get_training_sampling() -> dict:
        return sampling_policy()

    @html_router.get("/external/soccernet/full-analysis")
    def get_external_soccernet_full_analysis_page() -> HTMLResponse:
        html_path = _external_soccernet_ui_binding_root() / "analysis_product_ui_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="SoccerNet analysis product UI binding not ready")
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    @html_router.get("/external/soccertrack/{match_id}/analysis")
    def get_external_soccertrack_analysis_page(match_id: str) -> HTMLResponse:
        return HTMLResponse(content=_load_external_soccertrack_analysis_html(match_id))

    @html_router.get("/external/benchmark/report")
    def get_external_benchmark_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_external_benchmark_report_html())

    @html_router.get("/external/benchmark/decision")
    def get_external_benchmark_decision_surface_page() -> HTMLResponse:
        return HTMLResponse(content=_load_external_benchmark_decision_html())

    @html_router.get("/video-to-analysis/finish-line")
    def get_video_to_analysis_finish_line_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_finish_line_html())

    @html_router.get("/video-to-analysis/acceptance-report")
    def get_video_to_analysis_acceptance_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_acceptance_report_html())

    @html_router.get("/video-to-analysis/operator-handoff")
    def get_video_to_analysis_operator_handoff_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_operator_handoff_html())

    @html_router.get("/video-to-analysis/release-readout")
    def get_video_to_analysis_release_readout_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_release_readout_html())

    @html_router.get("/video-to-analysis/post-release-monitoring")
    def get_video_to_analysis_post_release_monitoring_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_post_release_monitoring_html())

    @html_router.get("/video-to-analysis/detector-evaluation-report")
    def get_video_to_analysis_detector_evaluation_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_detector_evaluation_report_html())

    @html_router.get("/video-to-analysis/promotion-review")
    def get_video_to_analysis_promotion_review_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_promotion_review_report_html())

    @html_router.get("/video-to-analysis/promoted-runtime-monitoring")
    def get_video_to_analysis_promoted_runtime_monitoring_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_promoted_runtime_monitoring_html())

    @html_router.get("/video-to-analysis/operator-dashboard")
    def get_video_to_analysis_operator_dashboard_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_operator_dashboard_html())

    @html_router.get("/video-to-analysis/real-video-scaleout-report")
    def get_video_to_analysis_real_video_scaleout_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_real_video_scaleout_report_html())

    @html_router.get("/video-to-analysis/bounded-next-sample-report")
    def get_video_to_analysis_bounded_next_sample_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_bounded_next_sample_report_html())

    return router, html_router


def attach_leftover_get_routes(app: FastAPI, storage: Storage) -> None:
    leftover, html = create_leftover_get_routers(storage)
    app.include_router(leftover, prefix="/api/workbench/dev")
    if leftover_http_enabled():
        app.include_router(leftover, prefix="/api")
        app.include_router(html, prefix="")
