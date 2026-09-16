from __future__ import annotations

import json
import importlib
from email.message import Message
from http.client import HTTPResponse
from http.server import ThreadingHTTPServer
from io import BytesIO
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import threading
from types import SimpleNamespace
from urllib.parse import quote

import pytest

import backend.scripts.serve_promoted_v6_manual_review_ui as review_ui
from backend.scripts.review_http import HttpRequestError, read_json_payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _bbox(frame_id: int) -> dict[str, float]:
    return {
        "x1": float(frame_id),
        "y1": float(frame_id + 1),
        "x2": float(frame_id + 10),
        "y2": float(frame_id + 11),
    }


def _review_item(frame_id: int, *, decision: str = "pending_review") -> dict[str, object]:
    return {
        "reviewItemId": f"review-{frame_id}",
        "candidateFrameId": f"candidate-{frame_id}",
        "windowId": f"window-{frame_id // 10}",
        "curationUnitId": f"window-{frame_id // 10}",
        "sourceClipId": "trimed-5min.mp4",
        "frameIndex": frame_id,
        "timestampSeconds": round(frame_id / 25.0, 3),
        "seedBBox": _bbox(frame_id),
        "decision": decision,
        "reviewedBBox": None,
        "lineageComplete": True,
        "lineage": {
            "baselineBallTruthLayersPath": "/baseline/ball_truth_layers.json",
            "baselineSelectedClusterDeltaPath": "/baseline/selected_cluster_delta.json",
            "promotedBallTruthLayersPath": "/promoted/ball_truth_layers.json",
            "promotedSelectedClusterDeltaPath": "/promoted/selected_cluster_delta.json",
        },
        "notes": "review item",
        "fileStem": f"trimed-5min.mp4__f{frame_id:06d}__candidate-{frame_id}",
    }


def _write_review_root(root: Path, items: list[dict[str, object]]) -> Path:
    review_root = root / "manual_review"
    frames_root = review_root / "review_frames"
    frames_root.mkdir(parents=True)
    for item in items:
        (frames_root / f"{item['fileStem']}.jpg").write_bytes(b"fake-jpeg")
    _write_json(
        review_root / "reviewed_label_overlay.json",
        {
            "batchName": "promoted_v6_manual_review_followthrough_v1",
            "reviewItemCount": len(items),
            "pendingReviewCount": sum(item.get("decision") == "pending_review" for item in items),
            "reviewedPositiveCount": 0,
            "reviewedNegativeCount": 0,
            "lineageCompleteCount": len(items),
            "reviewItems": items,
        },
    )
    _write_json(
        review_root / "review_frame_manifest.json",
        {
            "batchName": "promoted_v6_manual_review_followthrough_v1",
            "reviewFrameCount": len(items),
            "extractedImageCount": len(items),
            "imageExtractionStatus": "images_extracted",
            "reviewFrames": [
                {
                    "reviewItemId": item["reviewItemId"],
                    "candidateFrameId": item["candidateFrameId"],
                    "frameIndex": item["frameIndex"],
                    "imageExtracted": True,
                    "imagePath": str(frames_root / f"{item['fileStem']}.jpg"),
                }
                for item in items
            ],
        },
    )
    _write_json(
        review_root / "review_bundle_manifest.json",
        {
            "reviewedLabelOverlayPath": str(review_root / "reviewed_label_overlay.json"),
            "reviewFrameManifestPath": str(review_root / "review_frame_manifest.json"),
            "reviewFramesRoot": str(frames_root),
        },
    )
    return review_root


def test_load_review_state_reports_items_frames_and_progress(tmp_path: Path) -> None:
    review_root = _write_review_root(tmp_path, [_review_item(i) for i in range(100, 178)])

    state = review_ui.load_review_state(review_root=review_root)

    assert state["summary"]["reviewItemCount"] == 78
    assert state["summary"]["pendingReviewCount"] == 78
    assert state["summary"]["reviewedPositiveCount"] == 0
    assert state["summary"]["reviewedNegativeCount"] == 0
    assert state["reviewItems"][0]["reviewItemId"] == "review-100"
    assert state["reviewItems"][0]["imageUrl"] == "/review_frames/trimed-5min.mp4__f000100__candidate-100.jpg"
    assert state["bundleManifest"]["reviewedLabelOverlayPath"].endswith("reviewed_label_overlay.json")


def test_update_review_item_accept_seed_updates_counts_and_preserves_lineage(tmp_path: Path) -> None:
    review_root = _write_review_root(tmp_path, [_review_item(10), _review_item(20)])
    before = json.loads((review_root / "reviewed_label_overlay.json").read_text())
    original_lineage = before["reviewItems"][0]["lineage"]

    result = review_ui.update_review_item(
        review_root=review_root,
        review_item_id="review-10",
        decision="accept_seed",
        reviewed_bbox=None,
        reviewer_notes="looks right",
    )

    assert result["summary"]["pendingReviewCount"] == 1
    assert result["summary"]["reviewedPositiveCount"] == 1
    overlay = json.loads((review_root / "reviewed_label_overlay.json").read_text())
    updated = overlay["reviewItems"][0]
    untouched = overlay["reviewItems"][1]
    assert updated["decision"] == "accept_seed"
    assert updated["reviewedBBox"] is None
    assert updated["reviewerNotes"] == "looks right"
    assert updated["lineage"] == original_lineage
    assert untouched["decision"] == "pending_review"


def test_update_review_item_requires_valid_reviewed_box_for_adjust_bbox(tmp_path: Path) -> None:
    review_root = _write_review_root(tmp_path, [_review_item(30)])

    with pytest.raises(review_ui.ReviewUpdateError, match="adjust_bbox_requires_valid_reviewed_bbox"):
        review_ui.update_review_item(
            review_root=review_root,
            review_item_id="review-30",
            decision="adjust_bbox",
            reviewed_bbox={"x1": 10, "y1": 10, "x2": 5, "y2": 20},
        )

    overlay = json.loads((review_root / "reviewed_label_overlay.json").read_text())
    assert overlay["reviewItems"][0]["decision"] == "pending_review"


def test_update_review_item_allows_adjust_bbox_with_valid_box(tmp_path: Path) -> None:
    review_root = _write_review_root(tmp_path, [_review_item(40)])

    result = review_ui.update_review_item(
        review_root=review_root,
        review_item_id="review-40",
        decision="adjust_bbox",
        reviewed_bbox={"x1": 1.0, "y1": 2.0, "x2": 5.0, "y2": 8.0},
    )

    assert result["summary"]["pendingReviewCount"] == 0
    assert result["summary"]["reviewedPositiveCount"] == 1
    overlay = json.loads((review_root / "reviewed_label_overlay.json").read_text())
    assert overlay["reviewItems"][0]["reviewedBBox"] == {"x1": 1.0, "y1": 2.0, "x2": 5.0, "y2": 8.0}


def test_update_review_item_rejects_unknown_decision(tmp_path: Path) -> None:
    review_root = _write_review_root(tmp_path, [_review_item(50)])

    with pytest.raises(review_ui.ReviewUpdateError, match="unknown_review_decision"):
        review_ui.update_review_item(
            review_root=review_root,
            review_item_id="review-50",
            decision="bulk_accept_seed",
        )


def test_update_review_item_does_not_mutate_runtime_or_source_manifest(tmp_path: Path) -> None:
    review_root = _write_review_root(tmp_path, [_review_item(60)])
    runtime_default_path = tmp_path / "runtime" / "promoted_touchline_detector_candidate.json"
    source_manifest_path = tmp_path / "frozen_source_manifest.json"
    _write_json(runtime_default_path, {"candidate": "v6"})
    _write_json(source_manifest_path, {"sources": [{"clipId": "trimed-5min.mp4"}]})
    runtime_before = runtime_default_path.read_text()
    source_manifest_before = source_manifest_path.read_text()

    review_ui.update_review_item(
        review_root=review_root,
        review_item_id="review-60",
        decision="confirm_hard_negative",
    )

    assert runtime_default_path.read_text() == runtime_before
    assert source_manifest_path.read_text() == source_manifest_before


def test_run_resolution_gate_invokes_existing_resolution_batch(tmp_path: Path) -> None:
    review_root = _write_review_root(tmp_path, [_review_item(70, decision="accept_seed")])
    output_root = tmp_path / "resolution"
    retention_root = tmp_path / "retention"
    suite_root = tmp_path / "suite"
    _write_json(retention_root / "retention_delta_summary.json", {"acceptedRetentionRatio": 0.069})
    _write_json(suite_root / "suite_summary.json", {"sourceRobustnessOutcome": "source_robustness_partial"})

    result = review_ui.run_resolution_gate(
        review_root=review_root,
        output_root=output_root,
        retention_delta_root=retention_root,
        suite_root=suite_root,
    )

    assert result["summary"]["batchStatus"] == "review_resolved"
    assert result["summary"]["nextCorrectiveFamily"] == "reviewed_followthrough_selection_fix"
    assert (output_root / "reviewed_followthrough_truth_seed.json").exists()


def test_review_ui_script_runs_directly_in_dry_run_mode(tmp_path: Path) -> None:
    review_root = _write_review_root(tmp_path, [_review_item(80)])

    result = subprocess.run(
        [
            sys.executable,
            "backend/scripts/serve_promoted_v6_manual_review_ui.py",
            "--review-root",
            str(review_root),
            "--dry-run",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["reviewItemCount"] == 1
    assert payload["pendingReviewCount"] == 1


@pytest.fixture(params=[
    "serve_promoted_v6_manual_review_ui",
    "serve_v7_1_positive_diversity_review_ui",
    "serve_football_external_soccernet_detector_miss_review_ui",
])
def legacy_server(request, tmp_path: Path):
    """Run the actual handlers with only disposable review artifacts."""
    module = importlib.import_module(f"backend.scripts.{request.param}")
    root = tmp_path / "review"
    frames = root / "review_frames"
    frames.mkdir(parents=True)
    outside = tmp_path / "sentinel.jpg"
    outside.write_bytes(b"OUTSIDE_SENTINEL_DO_NOT_SERVE")
    sibling = tmp_path / "review-extra"
    sibling.mkdir()
    (sibling / "sentinel.jpg").write_bytes(outside.read_bytes())
    (frames / "ready.jpg").write_bytes(b"owned-image")
    (frames / "unlisted.jpg").write_bytes(outside.read_bytes())
    (frames / "linked.jpg").symlink_to(outside)
    (frames / "internal-link.jpg").symlink_to(frames / "unlisted.jpg")
    (frames / "linked-parent").symlink_to(tmp_path, target_is_directory=True)
    (frames / "directory.jpg").mkdir()
    os.mkfifo(frames / "pipe.jpg")
    (frames / "notes.txt").write_bytes(outside.read_bytes())
    image_names = ["ready.jpg", "linked.jpg", "internal-link.jpg", "linked-parent/sentinel.jpg", "missing.jpg",
                   "directory.jpg", "pipe.jpg", "notes.txt"]
    if module is review_ui:
        overlay = root / "reviewed_label_overlay.json"
        _write_json(overlay, {"reviewItems": [{"reviewItemId": "item", "decision": "pending_review"}]})
        _write_json(root / "review_frame_manifest.json", {"reviewFrames": [
            {"reviewItemId": "item", "imagePath": str(frames / name)} for name in image_names
        ]})
        _write_json(root / "review_bundle_manifest.json", {})
        handler = module.build_handler(review_root=root, ui_root=tmp_path / "ui")
        payload = {"decision": "accept_seed"}
        image_url = lambda path: "/review_frames/" + quote(path.name)
        root_flag = "--review-root"
    else:
        overlay = module._overlay_path(root)
        fields = ("reviewFrameImagePath", "reviewCropImagePath") if "diversity" in request.param else ("fullFrameImagePath", "cropImagePath")
        _write_json(overlay, {"reviewItems": [
            {"candidateId": "item", "reviewItemId": "item", "reviewStatus": "pending_review",
             fields[0]: str(frames / name), fields[1]: str(frames / name)}
            for name in image_names
        ]})
        handler = module.build_handler(candidate_root=root, ui_root=tmp_path / "ui")
        payload = {"reviewStatus": "pending_review", "reviewNotes": "saved"}
        image_url = lambda path: "/source-image?path=" + quote(str(path), safe="/")
        root_flag = "--candidate-root"
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_bytes(b"fixed-review-index")
    (ui / "private.txt").write_bytes(outside.read_bytes())
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield SimpleNamespace(server=server, module=module, root=root, root_flag=root_flag,
                              frames=frames, outside=outside, sibling=sibling, overlay=overlay,
                              payload=payload, image_url=image_url)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _raw_http(server, path: str, *, method="GET", headers=(), body=b"", timeout=1, host=None):
    """Keep the request target and framing verbatim (no URL normalization)."""
    with socket.create_connection(server.server_address, timeout=timeout) as connection:
        authority = host if host is not None else f"127.0.0.1:{server.server_port}"
        request = f"{method} {path} HTTP/1.1\r\nHost: {authority}\r\n"
        request += "".join(f"{name}: {value}\r\n" for name, value in headers)
        connection.sendall(request.encode("ascii") + b"\r\n" + body)
        response = HTTPResponse(connection)
        try:
            response.begin()
            return response.status, response.read()
        except (TimeoutError, ConnectionError) as exc:
            pytest.fail(f"handler failed to return a bounded HTTP response: {type(exc).__name__}")


@pytest.mark.parametrize("attack", [
    "static-parent", "static-encoded-parent", "static-absolute", "static-private",
    "absolute", "parent", "encoded-parent", "sibling-prefix", "unlisted",
    "symlink", "internal-symlink", "parent-symlink", "missing", "directory", "fifo", "non-image",
])
def test_http_never_discloses_unowned_or_non_regular_images(legacy_server, attack):
    # Break: restoring a static fallback, caller-path opens, or symlink-following reads.
    fixture = legacy_server
    paths = {
        "static-parent": "/../sentinel.jpg",
        "static-encoded-parent": "/%2e%2e/sentinel.jpg",
        "static-absolute": str(fixture.outside),
        "static-private": "/private.txt",
        "absolute": "/source-image?path=" + str(fixture.outside),
        "parent": "/source-image?path=" + str(fixture.frames) + "/../../sentinel.jpg",
        "encoded-parent": "/source-image?path=" + str(fixture.frames) + "/%2e%2e/%2e%2e/sentinel.jpg",
        "sibling-prefix": "/source-image?path=" + str(fixture.sibling / "sentinel.jpg"),
        "unlisted": fixture.image_url(fixture.frames / "unlisted.jpg"),
        "symlink": fixture.image_url(fixture.frames / "linked.jpg"),
        "internal-symlink": fixture.image_url(fixture.frames / "internal-link.jpg"),
        "parent-symlink": fixture.image_url(fixture.frames / "linked-parent/sentinel.jpg"),
        "missing": fixture.image_url(fixture.frames / "missing.jpg"),
        "directory": fixture.image_url(fixture.frames / "directory.jpg"),
        "fifo": fixture.image_url(fixture.frames / "pipe.jpg"),
        "non-image": fixture.image_url(fixture.frames / "notes.txt"),
    }
    if fixture.module is review_ui:
        paths.update({
            "absolute": "/review_frames/" + str(fixture.outside),
            "parent": "/review_frames/../../sentinel.jpg",
            "encoded-parent": "/review_frames/%2e%2e/%2e%2e/sentinel.jpg",
            "sibling-prefix": "/review_frames/../../review-extra/sentinel.jpg",
        })
    status, body = _raw_http(fixture.server, paths[attack])
    assert b"OUTSIDE_SENTINEL_DO_NOT_SERVE" not in body
    assert status in {400, 404}


def test_http_preserves_fixed_index_and_owned_image(legacy_server):
    # Break: rejecting every file request also hides legitimate review evidence.
    fixture = legacy_server
    assert _raw_http(fixture.server, "/") == (200, b"fixed-review-index")
    assert _raw_http(fixture.server, "/index.html") == (200, b"fixed-review-index")
    assert _raw_http(fixture.server, fixture.image_url(fixture.frames / "ready.jpg")) == (200, b"owned-image")


def test_http_refuses_image_replaced_with_symlink_at_open(legacy_server, monkeypatch):
    # Break: checking for symlinks before an ordinary open leaves a TOCTOU disclosure.
    fixture = legacy_server
    original_open = os.open
    replaced = False

    def replace_at_open(path, flags, *args, **kwargs):
        nonlocal replaced
        if path == "ready.jpg" and kwargs.get("dir_fd") is not None:
            image = fixture.frames / "ready.jpg"
            image.unlink()
            image.symlink_to(fixture.outside)
            replaced = True
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", replace_at_open)
    status, body = _raw_http(fixture.server, fixture.image_url(fixture.frames / "ready.jpg"))
    assert replaced
    assert status == 404
    assert b"OUTSIDE_SENTINEL_DO_NOT_SERVE" not in body


def test_promoted_image_urls_preserve_reserved_filename_characters(tmp_path: Path) -> None:
    # Break: a manifest filename containing a query/fragment delimiter is not routable.
    item = _review_item(1)
    item["fileStem"] = "frame &#+%"
    root = _write_review_root(tmp_path, [item])
    state = review_ui.load_review_state(review_root=root)
    assert state["reviewItems"][0]["imageUrl"] == "/review_frames/frame%20%26%23%2B%25.jpg"


@pytest.mark.parametrize("length", [None, "-1", "malformed", "65537", "0", "+2", "2, 2"])
def test_http_rejects_invalid_length_before_reading_or_mutation(legacy_server, length):
    # Break: int(Content-Length) plus unbounded/negative reads can wait or mutate.
    fixture = legacy_server
    before = fixture.overlay.read_bytes()
    headers = [] if length is None else [("Content-Length", length)]
    status, _ = _raw_http(fixture.server, "/api/review-items/item", method="POST", headers=headers)
    assert status in {400, 411, 413}
    if length is None:
        assert status == 411
    assert fixture.overlay.read_bytes() == before


def test_http_rejects_single_foreign_host(legacy_server):
    # Break: trusting any Host allows DNS rebinding to reach the local writer.
    fixture = legacy_server
    before = fixture.overlay.read_bytes()
    body = json.dumps(fixture.payload).encode()
    status, _ = _raw_http(fixture.server, "/api/review-items/item", method="POST",
                          host="evil.example", headers=[("Content-Length", str(len(body)))], body=body)
    assert status == 403
    assert fixture.overlay.read_bytes() == before


@pytest.mark.parametrize("port,host,origin,allowed", [
    (80, "127.0.0.1", "http://127.0.0.1", True),
    (80, "127.0.0.1:80", "http://127.0.0.1", True),
    (80, "127.0.0.1", "http://127.0.0.1:80", True),
    (80, "127.0.0.1:80", "http://127.0.0.1:80", True),
    (80, "localhost", "http://localhost:80", True),
    (80, "[::1]:80", "http://[::1]", True),
    (80, "127.0.0.1", "http://127.0.0.1:81", False),
    (80, "127.0.0.1:81", "http://127.0.0.1:81", False),
    (80, "evil.example", "http://evil.example", False),
    (80, "127.0.0.1", "http://localhost", False),
    (80, "127.0.0.1", "https://127.0.0.1", False),
    (8765, "127.0.0.1:8765", "http://127.0.0.1:8765", True),
    (8765, "127.0.0.1", "http://127.0.0.1", False),
])
def test_local_json_default_port_authority_equivalence(port, host, origin, allowed):
    # Break: literal :80 comparisons reject browser-canonical default-port saves.
    # Exercise the real shared helper without reserving privileged port 80.
    body = b'{"decision":"accept_seed"}'
    headers = Message()
    headers["Host"] = host
    headers["Origin"] = origin
    headers["Content-Length"] = str(len(body))
    handler = SimpleNamespace(headers=headers, rfile=BytesIO(body),
                              server=SimpleNamespace(server_port=port, server_address=("127.0.0.1", port)))
    if allowed:
        assert read_json_payload(handler) == {"decision": "accept_seed"}
    else:
        with pytest.raises(HttpRequestError) as error:
            read_json_payload(handler)
        assert error.value.status == 403
        assert handler.rfile.tell() == 0


@pytest.mark.parametrize("extra", [
    [("Host", "evil.example")], [("Origin", "https://evil.example")],
    [("Origin", "null")], [("Origin", "http://127.0.0.1:1")],
    [("Transfer-Encoding", "chunked")], [("Content-Length", "2")],
])
def test_http_rejects_foreign_browser_and_ambiguous_framing(legacy_server, extra):
    # Break: a foreign browser can write reviews; duplicate framing bypasses bounds.
    fixture = legacy_server
    before = fixture.overlay.read_bytes()
    body = json.dumps(fixture.payload).encode()
    status, _ = _raw_http(fixture.server, "/api/review-items/item", method="POST",
                          headers=[("Content-Length", str(len(body))), *extra], body=body)
    assert status in {400, 403}
    assert fixture.overlay.read_bytes() == before


@pytest.mark.parametrize("length", [None, 65536])
def test_http_accepts_bounded_local_json_and_persists_decision(legacy_server, length):
    # Break: an off-by-one body limit or Origin validation blocks valid local saves.
    fixture = legacy_server
    body = json.dumps(fixture.payload).encode()
    if length:
        body += b" " * (length - len(body))
    status, response = _raw_http(fixture.server, "/api/review-items/item", method="POST",
                                headers=[("Content-Length", str(len(body))),
                                         ("Origin", f"http://127.0.0.1:{fixture.server.server_port}")], body=body)
    assert status == 200
    item = json.loads(response)["reviewItem"]
    for key, value in fixture.payload.items():
        assert item[key] == value
    saved = json.loads(fixture.overlay.read_text())["reviewItems"][0]
    for key, value in fixture.payload.items():
        assert saved[key] == value


def test_http_times_out_incomplete_body_without_mutation(legacy_server):
    # Break: leaving accepted sockets without a read timeout ties up handler threads.
    fixture = legacy_server
    before = fixture.overlay.read_bytes()
    status, _ = _raw_http(fixture.server, "/api/review-items/item", method="POST",
                          headers=[("Content-Length", "20")], body=b"{", timeout=6)
    assert status == 408
    assert fixture.overlay.read_bytes() == before


@pytest.mark.parametrize("host", ["0.0.0.0", "192.0.2.1", "::", "example.com"])
def test_cli_refuses_non_loopback_before_loading_artifacts(legacy_server, host):
    # Break: an unauthenticated review writer can be bound to public interfaces.
    fixture = legacy_server
    result = subprocess.run(
        [sys.executable, fixture.module.__file__, "--host", host,
         fixture.root_flag, str(fixture.root / "nonexistent"), "--dry-run"],
        capture_output=True, text=True, timeout=5, check=False,
    )
    assert result.returncode != 0
    assert "error:" in result.stderr
    assert "loopback" in result.stderr.lower()


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_cli_binds_loopback_and_prints_usable_url(legacy_server, monkeypatch, capsys, host):
    # Break: valid loopback binding, including IPv6, must still start a usable local UI.
    if host == "::1" and not socket.has_ipv6:
        pytest.skip("IPv6 unavailable")
    fixture = legacy_server
    monkeypatch.setattr(sys, "argv", [fixture.module.__file__, "--host", host, "--port", "0",
                                     fixture.root_flag, str(fixture.root)])

    def stop_after_bind(server):
        assert server.socket.getsockname()[0] == ("127.0.0.1" if host == "localhost" else host)
        raise KeyboardInterrupt

    monkeypatch.setattr(ThreadingHTTPServer, "serve_forever", stop_after_bind)
    assert fixture.module.main() == 0
    printed = capsys.readouterr().out
    expected_host = "[::1]" if host == "::1" else "127.0.0.1"
    assert f"http://{expected_host}:" in printed


@pytest.mark.parametrize("outcome", ["success", "prepublication", "rolled_back", "uncertain"])
@pytest.mark.parametrize("close_fails", [False, True])
def test_http_distinguishes_safe_write_failure_from_uncertain_outcome(legacy_server, monkeypatch, outcome, close_fails):
    # Break: generic exceptions expose paths or invite retries after a failed rollback.
    fixture = legacy_server
    before = fixture.overlay.read_bytes()
    original_replace, original_fsync = os.replace, os.fsync
    original_close = os.close
    parent_fd = None
    published = False

    def replace_with_fault(*args, **kwargs):
        nonlocal published, parent_fd
        parent_fd = kwargs.get("src_dir_fd")
        if outcome == "prepublication" or (published and outcome == "uncertain"):
            raise OSError("/private/reviews/secret/replace-failed")
        original_replace(*args, **kwargs)
        published = True

    def fail_commit_sync(fd):
        if outcome != "success" and published and stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("/private/reviews/secret/fsync-failed")
        original_fsync(fd)

    def close_with_fault(fd):
        original_close(fd)
        if close_fails and fd == parent_fd:
            raise OSError("/private/reviews/secret/parent-close-failed")

    monkeypatch.setattr(os, "replace", replace_with_fault)
    monkeypatch.setattr(os, "fsync", fail_commit_sync)
    monkeypatch.setattr(os, "close", close_with_fault)
    body = json.dumps(fixture.payload).encode()
    status, response = _raw_http(fixture.server, "/api/review-items/item", method="POST",
                                headers=[("Content-Length", str(len(body)))], body=body)
    assert status == {"success": 200, "uncertain": 409}.get(outcome, 503)
    if outcome == "success":
        assert json.loads(response)["reviewItem"] == json.loads(fixture.overlay.read_text())["reviewItems"][0]
        assert fixture.overlay.read_bytes() != before
        return
    assert json.loads(response) == {"error": "review_write_outcome_uncertain_do_not_retry" if outcome == "uncertain"
                                  else "review_write_failed"}
    if outcome != "uncertain":
        assert fixture.overlay.read_bytes() == before
    else:
        assert fixture.overlay.read_bytes() != before
