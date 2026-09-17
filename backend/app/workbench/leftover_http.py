"""Leftover contract HTTP. Production keeps these off the public /api surface."""

from __future__ import annotations

import json
from typing import Iterable

from starlette.types import ASGIApp, Receive, Scope, Send

from .flags import feature_enabled

DEV_PREFIX = "/api/workbench/dev"

# POST handlers that discard client bodies (`del payload`) in main.py.
LEFTOVER_POST_PATHS = (
    "/api/evaluation/workflow",
    "/api/evaluation/protocol",
    "/api/evaluation/prerequisites",
    "/api/providers",
    "/api/dependencies",
    "/api/roster/promotion/{task}",
    "/api/support/bundle",
    "/api/geometry/landmarks",
    "/api/geometry/preview",
    "/api/geometry/zoom-cut",
    "/api/metrics/network-failure",
    "/api/assistance/repair",
    "/api/assistance/policy",
    "/api/experiments/{experiment}",
    "/api/identity/clusters/{cluster_id}",
    "/api/pause",
    "/api/flags/{name}/enabled",
    "/api/decode/fallback",
    "/api/cache/recompute",
    "/api/training/ledger",
    "/api/decode/pixels",
    "/api/costs/deployment",
    "/api/decode/frames",
    "/api/decode/first",
    "/api/decode/challengers",
    "/api/decode/probe",
    "/api/challengers",
    "/api/permissions/stale",
    "/api/heatmap",
    "/api/dossier/release",
    "/api/rates/four",
    "/api/ownership/hysteresis",
    "/api/reports/template",
    "/api/receipts/promotion",
    "/api/ownership/invalidate",
    "/api/worker/environment",
    "/api/cleanup/complete",
    "/api/upload/interrupt",
    "/api/access/signed",
    "/api/training/promote",
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
    "/api/matches/{match_id}/shots/quality",
    "/api/matches/{match_id}/artifacts/alongside",
    "/api/matches/{match_id}/tracklets",
    "/api/matches/{match_id}/shots/features",
)


def leftover_http_enabled() -> bool:
    return feature_enabled("leftover_http")


def _template_to_regex(path: str) -> str:
    import re

    return "^" + re.sub(r"\{[^/]+\}", r"[^/]+", path) + "$"


_LEFTOVER_POST_MATCHERS = tuple(_template_to_regex(path) for path in LEFTOVER_POST_PATHS)


def is_leftover_post_path(path: str) -> bool:
    import re

    return any(re.match(matcher, path) for matcher in _LEFTOVER_POST_MATCHERS)


class LeftoverHttpGate:
    """Serve leftover POSTs under /api/workbench/dev; 404 public leftover POSTs unless flagged."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        method = (scope.get("method") or "GET").upper()
        if path.startswith(DEV_PREFIX + "/") or path == DEV_PREFIX:
            remainder = path[len(DEV_PREFIX) :] or "/"
            rewritten = dict(scope)
            rewritten["path"] = "/api" + remainder if remainder.startswith("/") else "/api/" + remainder
            rewritten["leftover_dev"] = True  # type: ignore[typeddict-unknown-key]
            await self.app(rewritten, receive, send)
            return
        if (
            method == "POST"
            and is_leftover_post_path(path)
            and not leftover_http_enabled()
            and not scope.get("leftover_dev")
        ):
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
