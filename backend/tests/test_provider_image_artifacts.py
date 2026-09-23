"""W06: visual evidence must be a bounded source image, not FrameData JSON."""

import hashlib
import json
from io import BytesIO
import subprocess

import pytest
from PIL import Image

from backend.app.llm import build_prompt
from backend.app.provider_images import (
    ProviderImage, admit_decoded_image, load_image_manifest,
    resolve_provider_image, save_image_manifest, select_source_image_manifest,
)
from backend.app.workbench.artifacts import ArtifactStore
from backend.app.workbench.media import DecodedFrame, FfmpegFrameSource, resolve_trusted_executable


def _fixture(tmp_path):
    image = Image.new("RGB", (3, 2), "red")
    output = BytesIO()
    image.save(output, format="PNG")
    payload = output.getvalue()
    store = ArtifactStore(tmp_path / "artifacts")
    digest = store.put(payload, namespace="provider_images")
    reference = ProviderImage(
        matchId="match-1", generationId="gen-1", sourceSha256="a" * 64,
        sourceFrameId=8, ptsSeconds=0.5, sourceWidth=5, sourceHeight=4,
        crop=(1, 1, 4, 3), width=3, height=2, imageSha256=digest,
        imageBytes=len(payload), mimeType="image/png",
    )
    return store, reference, payload


def test_approved_source_image_resolves_exact_artifact(tmp_path):
    store, reference, payload = _fixture(tmp_path)
    assert resolve_provider_image(store, reference, match_id="match-1", generation_id="gen-1",
        source_sha256="a" * 64, source_frames={8: 0.5},
        approved_images={reference.imageSha256: reference}) == payload


@pytest.mark.parametrize("change", [
    {"generationId": "gen-2"}, {"sourceSha256": "b" * 64},
    {"sourceFrameId": 9}, {"ptsSeconds": 0.6},
    {"imageBytes": 1}, {"width": 2}, {"crop": (2, 1, 5, 3)},
])
def test_wrong_scope_frame_or_image_metadata_is_rejected(tmp_path, change):
    store, reference, _ = _fixture(tmp_path)
    changed = reference.model_copy(update=change)
    with pytest.raises(ValueError):
        resolve_provider_image(store, changed, match_id="match-1", generation_id="gen-1",
            source_sha256="a" * 64, source_frames={8: 0.5},
            approved_images={reference.imageSha256: reference})


def test_plain_frame_data_and_tampered_bytes_cannot_resolve(tmp_path):
    store, reference, _ = _fixture(tmp_path)
    with pytest.raises((TypeError, ValueError)):
        resolve_provider_image(store, {"frameId": 8, "timestamp": 0.5},
            match_id="match-1", generation_id="gen-1", source_sha256="a" * 64,
            source_frames={8: 0.5}, approved_images={reference.imageSha256: reference})
    (store.root / "provider_images" / reference.imageSha256).write_bytes(b"tampered")
    with pytest.raises(ValueError):
        resolve_provider_image(store, reference, match_id="match-1", generation_id="gen-1",
            source_sha256="a" * 64, source_frames={8: 0.5},
            approved_images={reference.imageSha256: reference})


def test_oversized_artifact_is_rejected_before_read(tmp_path, monkeypatch):
    store, reference, _ = _fixture(tmp_path)
    monkeypatch.setattr(store, "get", lambda *a, **k: pytest.fail("oversized read"))
    changed = reference.model_copy(update={"imageBytes": 5_000_001})
    with pytest.raises(ValueError):
        resolve_provider_image(store, changed, match_id="match-1", generation_id="gen-1",
            source_sha256="a" * 64, source_frames={8: 0.5},
            approved_images={reference.imageSha256: reference})


def test_artifact_store_enforces_actual_file_byte_limit(tmp_path):
    store, reference, payload = _fixture(tmp_path)
    with pytest.raises(ValueError, match="byte limit"):
        store.get(reference.imageSha256, namespace="provider_images", max_bytes=len(payload) - 1)


def test_unapproved_image_digest_is_rejected_before_read(tmp_path, monkeypatch):
    store, reference, _ = _fixture(tmp_path)
    monkeypatch.setattr(store, "get", lambda *a, **k: pytest.fail("unapproved read"))
    with pytest.raises(ValueError, match="not approved"):
        resolve_provider_image(store, reference, match_id="match-1", generation_id="gen-1",
            source_sha256="a" * 64, source_frames={8: 0.5},
            approved_images={})


def test_report_prompt_does_not_call_structured_frame_samples_images():
    prompt = build_prompt("tactical_report", [], approved_evidence={"frameSamples": [
        {"frameId": 8, "timestamp": 0.5}]})
    assert "Frame samples are structured observations, not image pixels" in prompt
    assert "Image references alone do not contain pixels" in prompt


def test_decoded_source_frame_is_saved_and_reopened_from_owned_manifest(tmp_path):
    source = tmp_path / "retained-source.bin"
    source.write_bytes(b"retained fixture source")
    store = ArtifactStore(tmp_path / "artifacts")
    frame = DecodedFrame(8, 500, 0.5, 3, 2, "rgb", 0,
        bytes((255, 0, 0, 0, 255, 0, 0, 0, 255)) * 2, "fixture")
    reference = admit_decoded_image(store, source, frame, match_id="match-1",
        generation_id="gen-1", crop=(1, 0, 3, 2))
    assert reference.sourceSha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert (reference.sourceFrameId, reference.ptsSeconds, reference.crop) == (8, 0.5, (1, 0, 3, 2))
    digest = save_image_manifest(store, [reference])
    images = load_image_manifest(store, digest, match_id="match-1", generation_id="gen-1",
        source_sha256=reference.sourceSha256, source_frames={8: 0.5})
    assert [item[0] for item in images] == [reference]
    with Image.open(BytesIO(images[0][1])) as image:
        assert image.size == (2, 2)
        assert image.getpixel((0, 0)) == (0, 255, 0)


def test_manifest_rejects_changed_source_and_unclocked_frame(tmp_path):
    source = tmp_path / "retained-source.bin"
    source.write_bytes(b"source")
    store = ArtifactStore(tmp_path / "artifacts")
    frame = DecodedFrame(8, None, None, 1, 1, "rgb", 0, b"\xff\x00\x00", "fixture",
        presentation_clock="missing")
    with pytest.raises(ValueError, match="source clock"):
        admit_decoded_image(store, source, frame, match_id="match-1", generation_id="gen-1")
    assert not (store.root / "provider_images").exists()


@pytest.mark.real_media
def test_real_decoded_frame_retains_source_pixels_and_clock(tmp_path):
    source = tmp_path / "source.mp4"
    subprocess.run([str(resolve_trusted_executable("ffmpeg")), "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=c=red:s=16x16:r=2:d=1", "-pix_fmt", "yuv420p",
        "-y", str(source)], check=True, timeout=20)
    frame = list(FfmpegFrameSource().iter_frames(source))[0]
    store = ArtifactStore(tmp_path / "artifacts")
    reference = admit_decoded_image(store, source, frame, match_id="match-1",
        generation_id="gen-1")
    digest = save_image_manifest(store, [reference])
    images = load_image_manifest(store, digest, match_id="match-1", generation_id="gen-1",
        source_sha256=reference.sourceSha256,
        source_frames={frame.source_frame_index: frame.presentation_time_seconds})
    with Image.open(BytesIO(images[0][1])) as image:
        red, green, blue = image.getpixel((8, 8))
        assert red > green * 3 and red > blue * 3


@pytest.mark.integration
@pytest.mark.real_media
def test_retained_video_manifest_joins_current_report_evidence(tmp_path):
    from backend.app.provider_gateway import ProviderGateway
    from backend.app.settings import ProcessingSettings
    from backend.app.storage import Storage
    from backend.tests.test_audit_v3_final_journey import _install_video
    from backend.tests.test_audit_v3_c03_reports import _interprets

    storage = Storage(tmp_path / "store")
    match_id = _install_video(storage, tmp_path)
    generation_id = storage.current_generation(match_id).generationId
    source = storage.get_match_input_path(match_id)
    frame = list(FfmpegFrameSource().iter_frames(source))[0]
    store = ArtifactStore(storage.storage_root / "artifacts")
    reference = admit_decoded_image(store, source, frame, match_id=match_id,
        generation_id=generation_id)
    manifest_digest = save_image_manifest(store, [reference])
    received = []
    def adapter(*args, **kwargs):
        received.append(kwargs["approved_evidence"])
        return _interprets(*args, **kwargs)
    gateway = ProviderGateway(storage, ProcessingSettings(), adapter_factory=lambda: adapter)
    plain, _ = gateway.build_evidence(match_id, generation_id, "tactical_report")
    with_images, _ = gateway.build_evidence(match_id, generation_id, "tactical_report",
        image_manifest_digest=manifest_digest)
    assert with_images.digest != plain.digest
    assert with_images.visual_images == (reference.model_dump(mode="json"),)
    gateway.execute(match_id, "tactical_report", body={"imageManifestDigest": manifest_digest})
    assert received[0]["visualImages"] == (reference.model_dump(mode="json"),)
    with pytest.raises(ValueError):
        gateway.build_evidence(match_id, generation_id, "tactical_report",
            image_manifest_digest="f" * 64)
    wrong_generation = save_image_manifest(store, [reference.model_copy(
        update={"generationId": "another-generation"})])
    with pytest.raises(ValueError, match="scope"):
        gateway.build_evidence(match_id, generation_id, "tactical_report",
            image_manifest_digest=wrong_generation)


@pytest.mark.integration
@pytest.mark.real_media
def test_text_only_spend_policy_cannot_admit_visual_request(tmp_path):
    from backend.app.provider_gateway import ProviderBudgetLedger, ProviderDenied, ProviderGateway
    from backend.app.settings import ProcessingSettings
    from backend.app.storage import Storage
    from backend.tests.test_audit_v3_c04_providers import fake_policy
    from backend.tests.test_audit_v3_final_journey import _install_video

    storage = Storage(tmp_path / "store")
    match_id = _install_video(storage, tmp_path)
    generation_id = storage.current_generation(match_id).generationId
    source = storage.get_match_input_path(match_id)
    frame = next(FfmpegFrameSource().iter_frames(source))
    artifacts = ArtifactStore(storage.storage_root / "artifacts")
    manifest_digest = save_image_manifest(artifacts, [admit_decoded_image(artifacts, source,
        frame, match_id=match_id, generation_id=generation_id)])
    config = storage.get_match(match_id).config.model_copy(deep=True)
    config.rights.cloudPermission = True
    config.rights.processingScope = "local_plus_burst"
    storage.update_match_config(match_id, config)

    def adapter(*_args, **_kwargs):
        pytest.fail("visual request reached text-only adapter")
    adapter.billing_contract_id = "synthetic-byte-token-v1"
    settings = ProcessingSettings(cloud_provider_enabled=True, cloud_provider_api_key="test-only",
        allowed_model_ids=("test-model",), cloud_model_id="test-model",
        provider_call_reservation=.25, provider_budget_limit=1,
        provider_spend_policy=fake_policy())
    gateway = ProviderGateway(storage, settings, adapter_factory=lambda: adapter,
        budget_ledger=ProviderBudgetLedger(storage.job_ledger.db_path, 1))
    with pytest.raises(ProviderDenied, match="CLOUD_SPEND_BOUND_UNQUALIFIED"):
        gateway.execute(match_id, "tactical_report", requested_provider="cloud",
            body={"requireProvider": True, "imageManifestDigest": manifest_digest})
    assert gateway.budget_ledger.reservations() == []


@pytest.mark.integration
@pytest.mark.real_media
def test_mock_astra_request_binds_exact_approved_image_and_reservation(tmp_path):
    import base64
    from backend.app.provider_adapters import parse_astra_response
    from backend.app.provider_billing import AstraSpendPolicy, ProviderResult, ProviderUsage
    from backend.app.provider_gateway import ProviderBudgetLedger, ProviderGateway
    from backend.app.report_contracts import ReportDraft
    from backend.app.settings import ProcessingSettings
    from backend.app.storage import Storage
    from backend.tests.test_audit_v3_final_journey import _install_video

    storage = Storage(tmp_path / "store")
    match_id = _install_video(storage, tmp_path)
    generation_id = storage.current_generation(match_id).generationId
    source = storage.get_match_input_path(match_id)
    frame = next(FfmpegFrameSource().iter_frames(source))
    artifacts = ArtifactStore(storage.storage_root / "artifacts")
    reference = admit_decoded_image(artifacts, source, frame,
        match_id=match_id, generation_id=generation_id)
    manifest_digest = save_image_manifest(artifacts, [reference])
    image_bytes = load_image_manifest(artifacts, manifest_digest, match_id=match_id,
        generation_id=generation_id, source_sha256=reference.sourceSha256,
        source_frames={reference.sourceFrameId: reference.ptsSeconds})[0][1]
    config = storage.get_match(match_id).config.model_copy(deep=True)
    config.rights.cloudPermission = True
    config.rights.processingScope = "local_plus_burst"
    storage.update_match_config(match_id, config)
    calls = []
    def adapter(*_args, **kwargs):
        calls.append(kwargs)
        request = kwargs["prepared_request"]
        bound = kwargs["execution_bound"]
        assert bound["requestSha256"] == hashlib.sha256(json.dumps(request,
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        assert request["input"][0]["content"][1]["image_url"] == (
            "data:image/png;base64," + base64.b64encode(image_bytes).decode())
        assert bound["maxImageTokens"] == 3001
        draft = ReportDraft(schemaVersion="report_draft_v1", matchId=match_id,
            generationId=generation_id, taskType="tactical_report")
        response = {"id": "mock-response", "model": "gpt-6-astra", "status": "completed",
            "service_tier": "default", "incomplete_details": None, "error": None,
            "output": [{"type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": draft.model_dump_json()}]}],
            "usage": {"input_tokens": 100, "output_tokens": 100, "total_tokens": 200}}
        parsed, _ = parse_astra_response(response, bound)
        return ProviderResult(parsed, ProviderUsage("mock-only", ".1", True))
    adapter.billing_contract_id = "astra-responses-v1"
    spend = AstraSpendPolicy(task_types=("tactical_report",), max_output_tokens=4096,
        input_price_per_million="20", output_price_per_million="75")
    settings = ProcessingSettings(cloud_provider_enabled=True, cloud_provider_api_key="test-only",
        allowed_model_ids=("gpt-6-astra",), cloud_model_id="gpt-6-astra",
        provider_call_reservation=20, provider_budget_limit=40, provider_spend_policy=spend)
    gateway = ProviderGateway(storage, settings, adapter_factory=lambda: adapter,
        budget_ledger=ProviderBudgetLedger(storage.job_ledger.db_path, 40))
    result = gateway.execute(match_id, "tactical_report", requested_provider="cloud",
        body={"requireProvider": True, "requestId": "mock-image", "imageManifestDigest": manifest_digest})
    assert result["policy"]["provider"] == "cloud"
    assert result["costSummary"]["actualTotal"] == .1
    assert gateway.execute(match_id, "tactical_report", requested_provider="cloud",
        body={"requireProvider": True, "requestId": "mock-image",
            "imageManifestDigest": manifest_digest})["reportId"] == result["reportId"]
    assert len(calls) == 1


@pytest.mark.integration
@pytest.mark.real_media
def test_selected_source_frame_seeks_to_exact_pts_and_rejects_misalignment(tmp_path):
    from backend.app.storage import Storage
    from backend.tests.test_audit_v3_final_journey import _install_video

    storage = Storage(tmp_path / "store")
    match_id = _install_video(storage, tmp_path)
    frames = storage.load_frames(match_id)
    # The journey fixture's declared 5 Hz observations differ from its 4 Hz source.
    generation_id = storage.current_generation(match_id).generationId
    with pytest.raises(ValueError, match="source frame identity"):
        select_source_image_manifest(storage, match_id, generation_id, [2])
    frames[2] = frames[2].model_copy(update={"timestamp": 0.25})
    storage.save_frames(match_id, frames)
    generation_id = storage.current_generation(match_id).generationId
    with pytest.raises(ValueError, match="source frame identity"):
        select_source_image_manifest(storage, match_id, generation_id, [2])
    frames[2] = frames[2].model_copy(update={"timestamp": 0.5})
    storage.save_frames(match_id, frames)
    old_generation_id = generation_id
    generation_id = storage.current_generation(match_id).generationId
    with pytest.raises(ValueError, match="generation"):
        select_source_image_manifest(storage, match_id, old_generation_id, [2])
    digest = select_source_image_manifest(storage, match_id, generation_id, [2])
    store = ArtifactStore(storage.storage_root / "artifacts")
    images = load_image_manifest(store, digest, match_id=match_id,
        generation_id=generation_id, source_sha256=storage.source_sha256(match_id),
        source_frames={2: 0.5})
    assert len(images) == 1
    assert (images[0][0].sourceFrameId, images[0][0].ptsSeconds) == (2, 0.5)
    source_frame = list(FfmpegFrameSource().iter_frames(storage.get_match_input_path(match_id)))[2]
    with Image.open(BytesIO(images[0][1])) as image:
        assert image.size == (1000, 600)
        expected = Image.frombytes("RGB", (1000, 600), source_frame.payload, "raw", "BGR")
        assert image.getpixel((500, 300)) == expected.getpixel((500, 300))
    with pytest.raises(ValueError, match="source frame"):
        select_source_image_manifest(storage, match_id, generation_id, [2, 2])


@pytest.mark.integration
@pytest.mark.real_media
def test_image_manifest_route_uses_retained_current_generation_without_cloud(tmp_path):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    from backend.tests.test_audit_v3_final_journey import _install_video

    app = create_app(storage_root=tmp_path / "store", run_jobs_inline=True)
    storage = app.state.storage
    match_id = _install_video(storage, tmp_path)
    generation_id = storage.current_generation(match_id).generationId
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.post(f"/api/matches/{match_id}/provider-images", json={
            "generationId": generation_id, "sourceFrameIds": [0]})
        assert response.status_code == 200, response.text
        digest = response.json()["imageManifestDigest"]
        package, _ = app.state.provider_gateway.build_evidence(match_id, generation_id,
            "tactical_report", image_manifest_digest=digest)
        assert package.visual_images[0]["sourceFrameId"] == 0
        rejected = client.post(f"/api/matches/{match_id}/provider-images", json={
            "generationId": generation_id, "sourceFrameIds": [0, 0]})
        assert rejected.status_code == 400
