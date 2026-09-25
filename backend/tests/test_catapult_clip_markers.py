"""Real media check for half-open, nonzero source-time clip export."""

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.schemas import CreateAnnotationRequest
from backend.app.storage import Storage
from backend.app.workbench.media import FfmpegProbe, resolve_trusted_executable
from backend.app.workbench.media_execution import MediaExecutionPolicy
from backend.tests.test_audit_v3_final_journey import _install_video


@pytest.mark.real_media
def test_exact_clip_keeps_only_source_frames_in_nonzero_half_open_interval(tmp_path: Path) -> None:
    ffmpeg = str(resolve_trusted_executable("ffmpeg"))
    source = tmp_path / "source.mp4"
    frames = []
    for index, color in enumerate(((240, 0, 0), (0, 240, 0), (0, 0, 240), (240, 240, 0))):
        frame = tmp_path / f"marker-{index}.ppm"
        frame.write_bytes(b"P6\n16 16\n255\n" + bytes(color) * (16 * 16))
        frames.append(frame)
    manifest = tmp_path / "frames.txt"
    manifest.write_text("".join(
        f"file '{frame.name}'\nduration {duration}\n"
        for frame, duration in zip(frames, (0.32, 0.48, 0.20, 0.40))
    ) + f"file '{frames[-1].name}'\n")
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(manifest), "-fps_mode", "vfr", "-pix_fmt", "yuv420p", "-y", str(source)],
                   check=True, timeout=20)
    output = tmp_path / "selected.mp4"
    FfmpegProbe().export_clip(source, output, start_seconds=0.32, duration_seconds=0.68, frame_exact=True)
    decoded = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(output),
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, check=True, timeout=20).stdout
    pixels = [decoded[index:index + 3] for index in range(0, len(decoded), 16 * 16 * 3)]
    assert len(pixels) == 2
    assert pixels[0][1] > pixels[0][0] and pixels[0][1] > pixels[0][2]  # green
    assert pixels[1][2] > pixels[1][0] and pixels[1][2] > pixels[1][1]  # blue



@pytest.mark.real_media
def test_exact_clip_keeps_first_frame_at_fractional_frame_rate(tmp_path: Path) -> None:
    ffmpeg = str(resolve_trusted_executable("ffmpeg"))
    colors = ((240, 0, 0), (0, 240, 0), (0, 0, 240), (240, 240, 0), (0, 240, 240), (240, 0, 240))
    for index, color in enumerate(colors):
        (tmp_path / f"frame-{index}.ppm").write_bytes(b"P6\n16 16\n255\n" + bytes(color) * (16 * 16))
    source = tmp_path / "source.mp4"
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-framerate", "30000/1001",
                    "-i", str(tmp_path / "frame-%d.ppm"), "-pix_fmt", "yuv420p", "-y", str(source)],
                   check=True, timeout=20)
    output = tmp_path / "selected.mp4"
    # Frame 2 starts at 2002/30000 s; rounding -ss to 0.067 would drop it.
    FfmpegProbe().export_clip(source, output, start_seconds=2 * 1001 / 30000,
                              duration_seconds=2 * 1001 / 30000, frame_exact=True)
    decoded = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(output),
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, check=True, timeout=20).stdout
    first = decoded[:3]
    assert first[2] > first[0] and first[2] > first[1]  # blue: source frame 2

@pytest.mark.integration
@pytest.mark.real_media
def test_saved_source_interval_downloads_playable_clip_and_rejects_unsaved_range(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "store")
    match_id = _install_video(storage, tmp_path)
    storage.submit_correction(match_id, kind="playlist_item", payload={
        "timestampStart": 0.25, "timestampEnd": 0.75,
        "sourceEndFrameExclusive": 3, "title": "Pressing cue", "notes": "Watch the release",
    })
    storage.create_annotation(match_id, CreateAnnotationRequest(
        type="note", frameStart=1, frameEnd=3, timestampStart=0.25,
        timestampEnd=0.75, text="Pressing cue",
    ))
    generation = storage.current_generation(match_id).generationId
    with TestClient(create_app(storage_root=storage.storage_root), base_url="http://127.0.0.1") as client:
        denied = client.get(f"/api/matches/{match_id}/edits/clip", params={
            "generationId": generation, "start": 0.0, "end": 0.25,
        })
        assert denied.status_code == 422, denied.text
        response = client.get(f"/api/matches/{match_id}/edits/clip", params={
            "generationId": generation, "start": 0.25, "end": 0.75,
        })
        exported = client.get(f"/api/matches/{match_id}/export/match.json", params={"generationId": generation})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.headers["x-generation-id"] == generation
    downloaded = tmp_path / "downloaded.mp4"
    downloaded.write_bytes(response.content)
    assert len(response.content) > 100
    assert FfmpegProbe().probe_identity(downloaded).durationSeconds is not None
    package = exported.json()
    assert package["generationId"] == generation
    assert package["corrections"][-1]["payload"]["title"] == "Pressing cue"
    assert package["corrections"][-1]["payload"]["notes"] == "Watch the release"
    assert package["annotations"][0]["text"] == "Pressing cue"
    reopened = Storage(storage.storage_root)
    assert reopened.edit_list_for_match(match_id, generation_id=generation)["intervals"] == [(0.25, 0.75)]
    assert reopened.list_annotations(match_id)[0].text == "Pressing cue"


@pytest.mark.integration
@pytest.mark.real_media
def test_saved_interval_exports_processed_wide_source(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "store")
    match_id = _install_video(storage, tmp_path, size="2048x600")
    storage.submit_correction(match_id, kind="playlist_item", payload={
        "timestampStart": 0.25, "timestampEnd": 0.75, "notes": "Wide source export",
    })
    generation = storage.current_generation(match_id).generationId
    with TestClient(create_app(storage_root=storage.storage_root), base_url="http://127.0.0.1") as client:
        response = client.get(f"/api/matches/{match_id}/edits/clip", params={
            "generationId": generation, "start": 0.25, "end": 0.75,
        })
    assert response.status_code == 200
    output = tmp_path / "export.mp4"
    output.write_bytes(response.content)
    assert FfmpegProbe(policy=MediaExecutionPolicy(max_width=4096)).probe_identity(output).width == 2048
