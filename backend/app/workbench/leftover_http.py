"""Leftover contract HTTP. Production keeps these off the public /api surface."""

from __future__ import annotations

import json
from typing import Iterable

from starlette.types import ASGIApp, Receive, Scope, Send

from .flags import feature_enabled

DEV_PREFIX = "/api/workbench/dev"

# Leftover contract POSTs isolated under /api/workbench/dev unless leftover_http is enabled.
LEFTOVER_POST_PATHS = (
    "/api/evaluation/workflow",
    "/api/evaluation/protocol",
    "/api/evaluation/prerequisites",
    "/api/research/tracks/{track_id:path}/execute",
    "/api/providers",
    "/api/dependencies",
    "/api/roster/promotion/{task}",
    "/api/support/bundle",
    "/api/geometry/contact",
    "/api/geometry/legacy",
    "/api/geometry/landmarks",
    "/api/geometry/preview",
    "/api/geometry/zoom-cut",
    "/api/metrics/network-failure",
    "/api/assistance/repair",
    "/api/assistance/policy",
    "/api/experiments/quality-gate",
    "/api/experiments/{experiment}",
    "/api/identity/promote",
    "/api/identity/clusters/{cluster_id}",
    "/api/pause",
    "/api/quota",
    "/api/worker/import",
    "/api/training/admit",
    "/api/research/paths",
    "/api/flags/{name}/enabled",
    "/api/detector",
    "/api/perception/tiles",
    "/api/sharing",
    "/api/media/colour",
    "/api/decode/wrap",
    "/api/decode/fallback",
    "/api/perception/preprocess",
    "/api/perception/score",
    "/api/perception/stratum",
    "/api/perception/ball-states",
    "/api/identity/preview",
    "/api/tracker",
    "/api/events/propose",
    "/api/events/score",
    "/api/cache/recompute",
    "/api/training/ledger",
    "/api/identity/repair",
    "/api/decode/crop",
    "/api/decode/cuts",
    "/api/decode/grid",
    "/api/decode/pixels",
    "/api/costs/deployment",
    "/api/metrics/spec",
    "/api/access/object",
    "/api/decode/sample",
    "/api/decode/pts",
    "/api/decode/proxy-pts",
    "/api/decode/interval",
    "/api/decode/frames",
    "/api/decode/first",
    "/api/decode/challengers",
    "/api/decode/probe",
    "/api/decode/export",
    "/api/challengers",
    "/api/permissions/stale",
    "/api/heatmap",
    "/api/reports/assemble",
    "/api/assistance/ground",
    "/api/assistance/select-evidence",
    "/api/metrics/legacy-zero",
    "/api/dossier/release",
    "/api/rates/four",
    "/api/ownership/hysteresis",
    "/api/metrics/possession-states",
    "/api/reports/template",
    "/api/receipts/promotion",
    "/api/ownership/invalidate",
    "/api/quantities/scores",
    "/api/worker/environment",
    "/api/cleanup/complete",
    "/api/upload/interrupt",
    "/api/access/signed",
    "/api/training/cycle",
    "/api/training/promote",
    "/api/training/pseudo",
    "/api/search",
    "/api/matches/{match_id}/heatmap",
    "/api/matches/{match_id}/players",
    "/api/matches/{match_id}/ownership",
    "/api/matches/{match_id}/package",
    "/api/matches/{match_id}/incidents/geometry",
    "/api/matches/{match_id}/metrics",
    "/api/matches/{match_id}/incidents/package",
    "/api/matches/{match_id}/incidents/review",
    "/api/matches/{match_id}/assistance/fallback",
    "/api/matches/{match_id}/identity",
    "/api/matches/{match_id}/cache",
    "/api/matches/{match_id}/records/migrate",
    "/api/matches/{match_id}/formation",
    "/api/matches/{match_id}/events/partition",
    "/api/matches/{match_id}/reports/provenance",
    "/api/matches/{match_id}/shots/quality",
    "/api/matches/{match_id}/artifacts/alongside",
    "/api/matches/{match_id}/tracklets",
    "/api/matches/{match_id}/shots/features",
)

# Leftover contract GETs isolated under /api/workbench/dev unless leftover_http is enabled.
LEFTOVER_GET_PATHS = (
    "/api/external/soccernet/full-analysis",
    "/external/soccernet/full-analysis",
    "/api/external/soccertrack/{match_id}/export/match.json",
    "/api/external/soccertrack/{match_id}/analysis",
    "/external/soccertrack/{match_id}/analysis",
    "/api/external/benchmark/report",
    "/external/benchmark/report",
    "/api/external/benchmark/decision",
    "/external/benchmark/decision",
    "/api/video-to-analysis/finish-line",
    "/video-to-analysis/finish-line",
    "/api/video-to-analysis/acceptance-report",
    "/video-to-analysis/acceptance-report",
    "/api/video-to-analysis/operator-handoff",
    "/video-to-analysis/operator-handoff",
    "/api/video-to-analysis/release-readout",
    "/video-to-analysis/release-readout",
    "/api/video-to-analysis/post-release-monitoring",
    "/video-to-analysis/post-release-monitoring",
    "/api/video-to-analysis/detector-evaluation-report",
    "/video-to-analysis/detector-evaluation-report",
    "/api/video-to-analysis/promotion-review",
    "/video-to-analysis/promotion-review",
    "/api/video-to-analysis/promoted-runtime-monitoring",
    "/video-to-analysis/promoted-runtime-monitoring",
    "/api/video-to-analysis/operator-dashboard",
    "/video-to-analysis/operator-dashboard",
    "/api/video-to-analysis/real-video-scaleout-report",
    "/video-to-analysis/real-video-scaleout-report",
    "/api/video-to-analysis/bounded-next-sample-report",
    "/video-to-analysis/bounded-next-sample-report",
    "/api/evaluation/measures",
    "/api/evaluation/workflow",
    "/api/evaluation/protocol",
    "/api/evaluation/prerequisites",
    "/api/research/lane",
    "/api/xt",
    "/api/credits",
    "/api/admission/{profile}",
    "/api/training/drills",
    "/api/rights",
    "/api/rights/licences",
    "/api/rights/datasets",
    "/api/rights/incident",
    "/api/providers",
    "/api/dependencies",
    "/api/telestration",
    "/api/roster",
    "/api/roster/labels",
    "/api/roster/video",
    "/api/roster/frontier",
    "/api/roster/promotion/{task}",
    "/api/risks",
    "/api/milestones",
    "/api/targets",
    "/api/decisions",
    "/api/residency",
    "/api/broker",
    "/api/vector",
    "/api/deployment/{mode}",
    "/api/recovery",
    "/api/scale/{matches}",
    "/api/privacy/dpia",
    "/api/gpu",
    "/api/native",
    "/api/security",
    "/api/assistance",
    "/api/decode/memory",
    "/api/reviewer",
    "/api/flow",
    "/api/identity",
    "/api/incidents/ladder",
    "/api/evaluation/hota",
    "/api/shots/tree",
    "/api/collaboration",
    "/api/media/stride",
    "/api/cache/tenancy",
    "/api/quantities/axes",
    "/api/timing/gpu",
    "/api/native/memory",
    "/api/capacity",
    "/api/repository",
    "/api/support/bundle",
    "/api/geometry/contact",
    "/api/geometry/legacy",
    "/api/geometry/landmarks",
    "/api/geometry/preview",
    "/api/metrics/network-failure",
    "/api/reports/held-out",
    "/api/storage/object",
    "/api/recovery/disk",
    "/api/recovery/restore",
    "/api/preemptible",
    "/api/experiments/{experiment}",
    "/api/timing/stages",
    "/api/identity/clusters/{cluster_id}",
    "/api/training/pools",
    "/api/flags/shadow/{name}",
    "/api/flags/{name}/enabled",
    "/api/quantities/display",
    "/api/metrics/round-trip",
    "/api/decode/frames",
    "/api/decode/challengers",
    "/api/challengers",
    "/api/permissions/stale",
    "/api/heatmap",
    "/api/dossier/release",
    "/api/rates/four",
    "/api/receipts/promotion",
    "/api/quantities/scores",
    "/api/access/signed",
    "/api/training/sampling",
)


def leftover_http_enabled() -> bool:
    return feature_enabled("leftover_http")


def _template_to_regex(path: str) -> str:
    import re

    return "^" + re.sub(r"\{[^/]+\}", r"[^/]+", path) + "$"


_LEFTOVER_POST_MATCHERS = tuple(_template_to_regex(path) for path in LEFTOVER_POST_PATHS)
_LEFTOVER_GET_MATCHERS = tuple(_template_to_regex(path) for path in LEFTOVER_GET_PATHS)


def is_leftover_post_path(path: str) -> bool:
    import re

    return any(re.match(matcher, path) for matcher in _LEFTOVER_POST_MATCHERS)


def is_leftover_get_path(path: str) -> bool:
    import re

    return any(re.match(matcher, path) for matcher in _LEFTOVER_GET_MATCHERS)


class LeftoverHttpGate:
    """Serve leftover HTTP under /api/workbench/dev; 404 public leftover routes unless flagged."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        method = (scope.get("method") or "GET").upper()
        if path.startswith(DEV_PREFIX + "/") or path == DEV_PREFIX:
            await self.app(scope, receive, send)
            return
        leftover_public = (
            (method == "POST" and is_leftover_post_path(path))
            or (method == "GET" and is_leftover_get_path(path))
        )
        if leftover_public and not leftover_http_enabled() and not scope.get("leftover_dev"):
            body = json.dumps({"detail": "leftover HTTP is namespaced under /api/workbench/dev"}).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)


def leftover_dev_paths(paths: Iterable[str]) -> list[str]:
    return [f"{DEV_PREFIX}{path[4:]}" if path.startswith("/api") else f"{DEV_PREFIX}{path}" for path in paths]
