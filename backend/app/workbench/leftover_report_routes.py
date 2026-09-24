from __future__ import annotations
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from ..storage import Storage
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
)

def _external_soccernet_ui_binding_root(storage: Storage) -> Path:
    return storage.storage_root / EXTERNAL_SOCCERNET_UI_BINDING_DIR


def _load_external_soccernet_view_model(storage: Storage) -> dict:
    view_model_path = _external_soccernet_ui_binding_root(storage) / "analysis_product_ui_view_model.json"
    if not view_model_path.exists():
        raise HTTPException(status_code=404, detail="SoccerNet analysis product UI binding not ready")
    return json.loads(view_model_path.read_text(encoding="utf-8"))


def _external_soccertrack_match_bundle_bridge_root(storage: Storage) -> Path:
    return storage.storage_root / EXTERNAL_SOCCERTRACK_MATCH_BUNDLE_BRIDGE_DIR


def _load_external_soccertrack_match_bundle(storage: Storage, match_id: str) -> dict:
    bundle_path = _external_soccertrack_match_bundle_bridge_root(storage) / "soccertrack_external_match_bundle.json"
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


def _external_soccertrack_ui_binding_root(storage: Storage) -> Path:
    return storage.storage_root / EXTERNAL_SOCCERTRACK_UI_BINDING_DIR


def _external_benchmark_ui_binding_root(storage: Storage) -> Path:
    return storage.storage_root / EXTERNAL_BENCHMARK_UI_BINDING_DIR


def _external_benchmark_decision_surface_root(storage: Storage) -> Path:
    return storage.storage_root / EXTERNAL_BENCHMARK_DECISION_SURFACE_DIR


def _video_to_analysis_finish_line_binding_root(storage: Storage) -> Path:
    return storage.storage_root / VIDEO_TO_ANALYSIS_FINISH_LINE_PRODUCT_BINDING_DIR


def _video_to_analysis_acceptance_report_binding_root(storage: Storage) -> Path:
    return storage.storage_root / VIDEO_TO_ANALYSIS_ACCEPTANCE_REPORT_BINDING_DIR


def _video_to_analysis_operator_handoff_binding_root(storage: Storage) -> Path:
    return storage.storage_root / VIDEO_TO_ANALYSIS_OPERATOR_HANDOFF_BINDING_DIR


def _video_to_analysis_release_readout_binding_root(storage: Storage) -> Path:
    return storage.storage_root / VIDEO_TO_ANALYSIS_RELEASE_READOUT_BINDING_DIR


def _video_to_analysis_post_release_monitoring_binding_root(storage: Storage) -> Path:
    return storage.storage_root / VIDEO_TO_ANALYSIS_POST_RELEASE_MONITORING_BINDING_DIR


def _video_to_analysis_detector_evaluation_report_binding_root(storage: Storage) -> Path:
    return storage.storage_root / VIDEO_TO_ANALYSIS_DETECTOR_EVALUATION_REPORT_BINDING_DIR


def _video_to_analysis_promotion_review_report_binding_root(storage: Storage) -> Path:
    return storage.storage_root / VIDEO_TO_ANALYSIS_PROMOTION_REVIEW_REPORT_BINDING_DIR


def _video_to_analysis_promoted_runtime_monitoring_binding_root(storage: Storage) -> Path:
    return storage.storage_root / VIDEO_TO_ANALYSIS_PROMOTED_RUNTIME_MONITORING_BINDING_DIR


def _video_to_analysis_operator_dashboard_binding_root(storage: Storage) -> Path:
    return storage.storage_root / VIDEO_TO_ANALYSIS_OPERATOR_DASHBOARD_BINDING_DIR


def _video_to_analysis_real_video_scaleout_report_binding_root(storage: Storage) -> Path:
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


def _video_to_analysis_bounded_next_sample_report_binding_root(storage: Storage) -> Path:
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


def _load_external_benchmark_view_model(storage: Storage) -> dict:
    binding_root = _external_benchmark_ui_binding_root(storage)
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


def _load_external_benchmark_report_html(storage: Storage) -> str:
    _load_external_benchmark_view_model(storage)
    html_path = _external_benchmark_ui_binding_root(storage) / "external_benchmark_product_ui_render_smoke.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="External benchmark product UI binding not ready")
    return html_path.read_text(encoding="utf-8")


def _load_external_benchmark_decision_view_model(storage: Storage) -> dict:
    surface_root = _external_benchmark_decision_surface_root(storage)
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


def _load_external_benchmark_decision_html(storage: Storage) -> str:
    _load_external_benchmark_decision_view_model(storage)
    html_path = _external_benchmark_decision_surface_root(storage) / "product_decision_surface_render_smoke.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="External benchmark decision surface not ready")
    return html_path.read_text(encoding="utf-8")


def _load_video_to_analysis_finish_line_view_model(storage: Storage) -> dict:
    binding_root = _video_to_analysis_finish_line_binding_root(storage)
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


def _load_video_to_analysis_finish_line_html(storage: Storage) -> str:
    _load_video_to_analysis_finish_line_view_model(storage)
    html_path = _video_to_analysis_finish_line_binding_root(storage) / "finish_line_product_render_smoke.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Video-to-analysis finish-line HTML not ready")
    return html_path.read_text(encoding="utf-8")


def _load_video_to_analysis_acceptance_report_view_model(storage: Storage) -> dict:
    binding_root = _video_to_analysis_acceptance_report_binding_root(storage)
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


def _load_video_to_analysis_acceptance_report_html(storage: Storage) -> str:
    _load_video_to_analysis_acceptance_report_view_model(storage)
    html_path = _video_to_analysis_acceptance_report_binding_root(storage) / "acceptance_report_render_smoke.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Video-to-analysis acceptance report HTML not ready")
    return html_path.read_text(encoding="utf-8")


def _load_video_to_analysis_operator_handoff_view_model(storage: Storage) -> dict:
    binding_root = _video_to_analysis_operator_handoff_binding_root(storage)
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


def _load_video_to_analysis_operator_handoff_html(storage: Storage) -> str:
    _load_video_to_analysis_operator_handoff_view_model(storage)
    html_path = _video_to_analysis_operator_handoff_binding_root(storage) / "operator_handoff_render_smoke.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Video-to-analysis operator handoff HTML not ready")
    return html_path.read_text(encoding="utf-8")


def _load_video_to_analysis_release_readout_view_model(storage: Storage) -> dict:
    binding_root = _video_to_analysis_release_readout_binding_root(storage)
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


def _load_video_to_analysis_release_readout_html(storage: Storage) -> str:
    _load_video_to_analysis_release_readout_view_model(storage)
    html_path = _video_to_analysis_release_readout_binding_root(storage) / "release_readout_render_smoke.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Video-to-analysis release readout HTML not ready")
    return html_path.read_text(encoding="utf-8")


def _load_video_to_analysis_post_release_monitoring_view_model(storage: Storage) -> dict:
    binding_root = _video_to_analysis_post_release_monitoring_binding_root(storage)
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


def _load_video_to_analysis_post_release_monitoring_html(storage: Storage) -> str:
    _load_video_to_analysis_post_release_monitoring_view_model(storage)
    html_path = _video_to_analysis_post_release_monitoring_binding_root(storage) / "post_release_monitoring_render_smoke.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Video-to-analysis post-release monitoring HTML not ready")
    return html_path.read_text(encoding="utf-8")


def _load_video_to_analysis_detector_evaluation_report_view_model(storage: Storage) -> dict:
    binding_root = _video_to_analysis_detector_evaluation_report_binding_root(storage)
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


def _load_video_to_analysis_detector_evaluation_report_html(storage: Storage) -> str:
    _load_video_to_analysis_detector_evaluation_report_view_model(storage)
    html_path = _video_to_analysis_detector_evaluation_report_binding_root(storage) / "detector_evaluation_report_render_smoke.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Video-to-analysis detector evaluation report HTML not ready")
    return html_path.read_text(encoding="utf-8")


def _load_video_to_analysis_promotion_review_report_view_model(storage: Storage) -> dict:
    binding_root = _video_to_analysis_promotion_review_report_binding_root(storage)
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


def _load_video_to_analysis_promotion_review_report_html(storage: Storage) -> str:
    _load_video_to_analysis_promotion_review_report_view_model(storage)
    html_path = _video_to_analysis_promotion_review_report_binding_root(storage) / "promotion_review_report_render_smoke.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Video-to-analysis promotion review HTML not ready")
    return html_path.read_text(encoding="utf-8")


def _load_video_to_analysis_promoted_runtime_monitoring_view_model(storage: Storage) -> dict:
    binding_root = _video_to_analysis_promoted_runtime_monitoring_binding_root(storage)
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


def _load_video_to_analysis_promoted_runtime_monitoring_html(storage: Storage) -> str:
    _load_video_to_analysis_promoted_runtime_monitoring_view_model(storage)
    html_path = _video_to_analysis_promoted_runtime_monitoring_binding_root(storage) / "promoted_runtime_monitoring_render_smoke.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Video-to-analysis promoted runtime monitoring HTML not ready")
    return html_path.read_text(encoding="utf-8")


def _load_video_to_analysis_operator_dashboard_view_model(storage: Storage) -> dict:
    binding_root = _video_to_analysis_operator_dashboard_binding_root(storage)
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


def _load_video_to_analysis_operator_dashboard_html(storage: Storage) -> str:
    _load_video_to_analysis_operator_dashboard_view_model(storage)
    html_path = _video_to_analysis_operator_dashboard_binding_root(storage) / "operator_dashboard_render_smoke.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Video-to-analysis operator dashboard HTML not ready")
    return html_path.read_text(encoding="utf-8")


def _load_video_to_analysis_real_video_scaleout_report_view_model(storage: Storage) -> dict:
    binding_root = _video_to_analysis_real_video_scaleout_report_binding_root(storage)
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


def _load_video_to_analysis_real_video_scaleout_report_html(storage: Storage) -> str:
    _load_video_to_analysis_real_video_scaleout_report_view_model(storage)
    html_path = _video_to_analysis_real_video_scaleout_report_binding_root(storage) / "real_video_scaleout_report_render_smoke.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Video-to-analysis real-video scaleout report HTML not ready")
    return html_path.read_text(encoding="utf-8")


def _load_video_to_analysis_bounded_next_sample_report_view_model(storage: Storage) -> dict:
    binding_root = _video_to_analysis_bounded_next_sample_report_binding_root(storage)
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


def _load_video_to_analysis_bounded_next_sample_report_html(storage: Storage) -> str:
    _load_video_to_analysis_bounded_next_sample_report_view_model(storage)
    html_path = _video_to_analysis_bounded_next_sample_report_binding_root(storage) / "bounded_next_sample_report_render_smoke.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Video-to-analysis bounded next-sample report HTML not ready")
    return html_path.read_text(encoding="utf-8")


def _load_external_soccertrack_view_model(storage: Storage, match_id: str) -> dict:
    binding_root = _external_soccertrack_ui_binding_root(storage)
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


def _load_external_soccertrack_analysis_html(storage: Storage, match_id: str) -> str:
    _load_external_soccertrack_view_model(storage, match_id)
    html_path = _external_soccertrack_ui_binding_root(storage) / "analysis_product_ui_render_smoke.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="SoccerTrack analysis product UI binding not ready")
    return html_path.read_text(encoding="utf-8")


def register_external_report_routes(router: APIRouter, html_router: APIRouter, storage: Storage) -> None:
    @router.get("/external/soccernet/full-analysis")
    def get_external_soccernet_full_analysis() -> dict:
        return _load_external_soccernet_view_model(storage)


    @router.get("/external/soccertrack/{match_id}/export/match.json")
    def export_external_soccertrack_match_json(match_id: str) -> dict:
        return _load_external_soccertrack_match_bundle(storage, match_id)


    @router.get("/external/soccertrack/{match_id}/analysis")
    def get_external_soccertrack_analysis(match_id: str) -> dict:
        return _load_external_soccertrack_view_model(storage, match_id)


    @router.get("/external/benchmark/report")
    def get_external_benchmark_report() -> dict:
        return _load_external_benchmark_view_model(storage)


    @router.get("/external/benchmark/decision")
    def get_external_benchmark_decision_surface() -> dict:
        return _load_external_benchmark_decision_view_model(storage)


    @html_router.get("/external/soccernet/full-analysis")
    def get_external_soccernet_full_analysis_page() -> HTMLResponse:
        html_path = _external_soccernet_ui_binding_root(storage) / "analysis_product_ui_render_smoke.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="SoccerNet analysis product UI binding not ready")
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


    @html_router.get("/external/soccertrack/{match_id}/analysis")
    def get_external_soccertrack_analysis_page(match_id: str) -> HTMLResponse:
        return HTMLResponse(content=_load_external_soccertrack_analysis_html(storage, match_id))


    @html_router.get("/external/benchmark/report")
    def get_external_benchmark_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_external_benchmark_report_html(storage))


    @html_router.get("/external/benchmark/decision")
    def get_external_benchmark_decision_surface_page() -> HTMLResponse:
        return HTMLResponse(content=_load_external_benchmark_decision_html(storage))



def register_video_report_routes(router: APIRouter, html_router: APIRouter, storage: Storage) -> None:
    @router.get("/video-to-analysis/finish-line")
    def get_video_to_analysis_finish_line() -> dict:
        return _load_video_to_analysis_finish_line_view_model(storage)


    @router.get("/video-to-analysis/acceptance-report")
    def get_video_to_analysis_acceptance_report() -> dict:
        return _load_video_to_analysis_acceptance_report_view_model(storage)


    @router.get("/video-to-analysis/operator-handoff")
    def get_video_to_analysis_operator_handoff() -> dict:
        return _load_video_to_analysis_operator_handoff_view_model(storage)


    @router.get("/video-to-analysis/release-readout")
    def get_video_to_analysis_release_readout() -> dict:
        return _load_video_to_analysis_release_readout_view_model(storage)


    @router.get("/video-to-analysis/post-release-monitoring")
    def get_video_to_analysis_post_release_monitoring() -> dict:
        return _load_video_to_analysis_post_release_monitoring_view_model(storage)


    @router.get("/video-to-analysis/detector-evaluation-report")
    def get_video_to_analysis_detector_evaluation_report() -> dict:
        return _load_video_to_analysis_detector_evaluation_report_view_model(storage)


    @router.get("/video-to-analysis/promotion-review")
    def get_video_to_analysis_promotion_review_report() -> dict:
        return _load_video_to_analysis_promotion_review_report_view_model(storage)


    @router.get("/video-to-analysis/promoted-runtime-monitoring")
    def get_video_to_analysis_promoted_runtime_monitoring() -> dict:
        return _load_video_to_analysis_promoted_runtime_monitoring_view_model(storage)


    @router.get("/video-to-analysis/operator-dashboard")
    def get_video_to_analysis_operator_dashboard() -> dict:
        return _load_video_to_analysis_operator_dashboard_view_model(storage)


    @router.get("/video-to-analysis/real-video-scaleout-report")
    def get_video_to_analysis_real_video_scaleout_report() -> dict:
        return _load_video_to_analysis_real_video_scaleout_report_view_model(storage)


    @router.get("/video-to-analysis/bounded-next-sample-report")
    def get_video_to_analysis_bounded_next_sample_report() -> dict:
        return _load_video_to_analysis_bounded_next_sample_report_view_model(storage)


    @html_router.get("/video-to-analysis/finish-line")
    def get_video_to_analysis_finish_line_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_finish_line_html(storage))


    @html_router.get("/video-to-analysis/acceptance-report")
    def get_video_to_analysis_acceptance_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_acceptance_report_html(storage))


    @html_router.get("/video-to-analysis/operator-handoff")
    def get_video_to_analysis_operator_handoff_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_operator_handoff_html(storage))


    @html_router.get("/video-to-analysis/release-readout")
    def get_video_to_analysis_release_readout_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_release_readout_html(storage))


    @html_router.get("/video-to-analysis/post-release-monitoring")
    def get_video_to_analysis_post_release_monitoring_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_post_release_monitoring_html(storage))


    @html_router.get("/video-to-analysis/detector-evaluation-report")
    def get_video_to_analysis_detector_evaluation_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_detector_evaluation_report_html(storage))


    @html_router.get("/video-to-analysis/promotion-review")
    def get_video_to_analysis_promotion_review_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_promotion_review_report_html(storage))


    @html_router.get("/video-to-analysis/promoted-runtime-monitoring")
    def get_video_to_analysis_promoted_runtime_monitoring_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_promoted_runtime_monitoring_html(storage))


    @html_router.get("/video-to-analysis/operator-dashboard")
    def get_video_to_analysis_operator_dashboard_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_operator_dashboard_html(storage))


    @html_router.get("/video-to-analysis/real-video-scaleout-report")
    def get_video_to_analysis_real_video_scaleout_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_real_video_scaleout_report_html(storage))


    @html_router.get("/video-to-analysis/bounded-next-sample-report")
    def get_video_to_analysis_bounded_next_sample_report_page() -> HTMLResponse:
        return HTMLResponse(content=_load_video_to_analysis_bounded_next_sample_report_html(storage))
