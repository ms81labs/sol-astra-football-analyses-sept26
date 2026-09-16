# SoccerTrack GSR Coordinate Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream actual SoccerTrack v2 GSR player coordinates from both retained halves into a reference-only external match bundle.

**Architecture:** Extend the existing adapter with a bounded standard-library iterator for the shipped SoccerNet-COCO `annotations` array, then pass normalized reference frames through the existing canonical fixture into the existing bridge. Preserve metric coordinates and source identity/team fields; label every exported frame as ground truth that was not used for inference.

**Tech Stack:** Python 3.12 standard library, pytest, existing JSON artifacts and release verifier

**Spec:** `docs/superpowers/specs/2026-09-13-soccertrack-gsr-coordinate-adapter-design.md`

## Global Constraints

- Follow the shipped COCO-style GSR bytes, not the older flat-record description.
- Read fixed-size chunks and cap one decoded annotation at 8 MiB.
- Read exactly 20 requested frames from each retained half for the bounded real-data check.
- Preserve centre-origin metres without clipping; normalized coordinates are derived display values.
- Keep source `left`/`right`; do not invent `my_team`/`enemy` assignment.
- Reference labels must never seed video inference.
- Add no dependency and perform no download, training, model promotion, provider call, or runtime-default mutation.

---

### Task 1: Stream and normalize shipped GSR annotations

**Files:**
- Modify: `backend/scripts/run_football_external_soccertrack_adapter_smoke_test.py`
- Modify: `backend/tests/test_run_football_external_soccertrack_adapter_smoke_test.py`

**Interfaces:**
- Produces: `_iter_json_array(stream, key, chunk_size)` yielding one JSON object at a time.
- Produces: `_stream_gsr_half(row, half, start_frame=0, frame_count=20)` returning `(frames, audit)`.
- Produces: `canonical_external_match_fixture.json.gsrFrames` and aggregate GSR counts.

- [x] **Step 1: Add shipped-shape fixture data and failing assertions**

In the existing test helper, write one compact COCO-style GSR file per half:

```python
{
    "info": {"frame_rate": 25, "seq_length": 3},
    "images": [{"image_id": "3000001"}, {"image_id": "3000002"}],
    "annotations": [
        {
            "id": "300000001",
            "image_id": "3000001",
            "track_id": 7,
            "supercategory": "object",
            "category_id": 1,
            "attributes": {"role": "player", "jersey": "9", "team": "left", "player_id": 11709209},
            "bbox_image": {"x": 100, "y": 200, "x_center": 110.0, "y_center": 220.0, "w": 20, "h": 40},
            "bbox_pitch": {
                "x_bottom_left": -52.5, "y_bottom_left": 34.0,
                "x_bottom_middle": -52.5, "y_bottom_middle": 34.0,
                "x_bottom_right": -52.5, "y_bottom_right": 34.0
            },
            "bbox_pitch_raw": {}
        },
        {
            "id": "300000101",
            "image_id": "3000002",
            "track_id": 7,
            "supercategory": "object",
            "category_id": 1,
            "attributes": {"role": "player", "jersey": "9", "team": "left", "player_id": 11709209},
            "bbox_image": {"x": 101, "y": 200, "x_center": 111.0, "y_center": 220.0, "w": 20, "h": 40},
            "bbox_pitch": {
                "x_bottom_left": 0.0, "y_bottom_left": 0.0,
                "x_bottom_middle": 0.0, "y_bottom_middle": 0.0,
                "x_bottom_right": 0.0, "y_bottom_right": 0.0
            },
            "bbox_pitch_raw": {}
        }
    ],
    "categories": []
}
```

Point each `halfFiles` row at its synthetic `sourcePath`. Assert two halves, four total frames, four entities, source `image_id`, half-relative timestamps, opaque `playerId`, team/role/jersey, exact metric corners/centre, and normalized `(-52.5, 34) -> (0, 0)` and `(0, 0) -> (50, 50)`.

Add a focused iterator test using a small `chunk_size` so keys and objects cross read boundaries. Append a valid out-of-window annotation followed by malformed trailing text; assert the requested window returns before consuming the malformed tail.

Run:

```bash
PATH=/tmp/football-audit-fixes-venv/bin:$PATH python3 -m pytest -q backend/tests/test_run_football_external_soccertrack_adapter_smoke_test.py
```

Expected: FAIL because the canonical fixture has no `gsrFrames` and the streaming functions do not exist.

- [x] **Step 2: Implement the minimal bounded iterator and mapping**

Use `json.JSONDecoder.raw_decode` over a discarded-prefix buffer. Require the `annotations` marker and opening array, reject malformed EOF, and raise if an undecoded value exceeds `8 * 1024 * 1024` bytes.

Decode the six-digit frame suffix with:

```python
text = str(image_id)
if len(text) < 7 or not text.isdigit():
    raise ValueError("SoccerTrack image_id must contain a sequence prefix and six-digit frame suffix")
frame_index = int(text[-6:]) - 1
```

Map usable entity annotations to:

```python
{
    "trackId": int(annotation["track_id"]),
    "playerId": None if attributes.get("player_id") is None else str(attributes["player_id"]),
    "role": str(attributes["role"]),
    "jerseyNumber": None if attributes.get("jersey") in (None, "") else int(attributes["jersey"]),
    "teamSide": attributes.get("team"),
    "pitchPositionMeters": {"x": x_m, "y": y_m},
    "pitchPositionNormalized": {
        "x": (x_m + 52.5) / 105.0 * 100.0,
        "y": (34.0 - y_m) / 68.0 * 100.0,
    },
    "imageBbox": annotation.get("bbox_image"),
}
```

Group by half/frame, preserve frames with omitted-position counts, require ordered frame IDs, and stop at the first annotation beyond the window. Return aggregate frame/entity/omission counts from `_gsr_audit`; pass `gsrFrames` into `_canonical_fixture`.

- [x] **Step 3: Verify GREEN and adapter regressions**

Run:

```bash
PATH=/tmp/football-audit-fixes-venv/bin:$PATH python3 -m pytest -q backend/tests/test_run_football_external_soccertrack_adapter_smoke_test.py backend/tests/test_run_football_external_soccertrack_sample_fixture_materialization.py
```

Expected: all tests pass, including the existing blocker routing.

### Task 2: Populate the external match bundle from GSR ground truth

**Files:**
- Modify: `backend/scripts/run_football_external_soccertrack_match_bundle_bridge_smoke.py`
- Modify: `backend/tests/test_run_football_external_soccertrack_match_bundle_bridge_smoke.py`
- Modify: `backend/tests/test_external_soccertrack_product_route.py`

**Interfaces:**
- Consumes: `canonical_external_match_fixture.json.gsrFrames` from Task 1.
- Produces: `soccertrack_external_match_bundle.json.frames[*].players` with reference-only provenance.

- [x] **Step 1: Add failing bridge and route assertions**

Replace the test fixture's MOT-only frame with two `gsrFrames`, one per half, each containing an entity from Task 1. Assert:

```python
assert bundle["provenance"]["groundTruthReferenceOnly"] is True
assert bundle["provenance"]["referenceLabelsUsedForInference"] is False
assert bundle["artifactAvailability"]["gsrGroundTruth"] is True
assert bundle["frames"][0]["source"] == "soccertrack_gsr_ground_truth"
assert bundle["frames"][0]["referenceOnly"] is True
assert bundle["frames"][0]["players"][0]["pitchPositionMeters"] == {"x": -52.5, "y": 34.0}
assert bundle["frames"][0]["players"][0]["x"] == 0.0
assert bundle["frames"][0]["players"][0]["y"] == 0.0
assert bundle["frames"][0]["players"][0]["sourceTeam"] == "left"
assert bundle["frames"][0]["frameId"] != bundle["frames"][1]["frameId"]
```

Update the route fixture to carry the same provenance flags and a populated player. Assert the API returns them unchanged.

Run:

```bash
PATH=/tmp/football-audit-fixes-venv/bin:$PATH python3 -m pytest -q backend/tests/test_run_football_external_soccertrack_match_bundle_bridge_smoke.py backend/tests/test_external_soccertrack_product_route.py
```

Expected: FAIL because the bridge still builds frames from `motSampleFrames` with `players: []`.

- [x] **Step 2: Map GSR frames and harden the bridge audit**

Require non-empty `gsrFrames` in `_adapter_ready`. Map each reference frame to a unique integer ID `half * 1_000_000 + frameIndex`, preserve `half` and `timestampSecondsInHalf`, and copy each entity into `players` with `id=trackId`, normalized `x/y`, `confidence=1.0`, opaque `playerId`, `sourceTeam`, `role`, `jerseyNumber`, and `pitchPositionMeters`.

Set frame `source="soccertrack_gsr_ground_truth"` and `referenceOnly=true`. Set bundle provenance and `artifactAvailability.gsrGroundTruth` as asserted above. Extend `_contract_audit` so readiness requires populated coordinates and both reference-safety flags.

- [x] **Step 3: Verify GREEN and route regressions**

Run:

```bash
PATH=/tmp/football-audit-fixes-venv/bin:$PATH python3 -m pytest -q \
  backend/tests/test_run_football_external_soccertrack_match_bundle_bridge_smoke.py \
  backend/tests/test_external_soccertrack_product_route.py \
  backend/tests/test_run_football_external_soccertrack_product_route_smoke.py
```

Expected: all tests pass.

### Task 3: Correct readiness evidence and run the retained real-data window

**Files:**
- Modify: `docs/reports/2026-09-13-football-analysis-readiness.md`
- Modify: `docs/status/current.md`
- Generated under ignored storage: adapter and bridge artifacts for match `117092`

**Interfaces:**
- Consumes: both retained 2.7 GB GSR halves.
- Produces: bounded actual coordinate counts and corrected documentation that does not claim inference accuracy.

- [x] **Step 1: Correct the report's GSR schema evidence**

In evidence gap 2, state that the retained files use the shipped SoccerNet-COCO structure and that the older cached flat-schema document is stale. Note prefixed string image IDs, nested attributes, bottom-middle metric positions, half-relative timing, and the fact that these labels are ground truth rather than predictions.

- [x] **Step 2: Run the adapter and bridge on retained data**

Run:

```bash
PATH=/tmp/football-audit-fixes-venv/bin:$PATH python3 -m backend.scripts.run_football_external_soccertrack_adapter_smoke_test
PATH=/tmp/football-audit-fixes-venv/bin:$PATH python3 -m backend.scripts.run_football_external_soccertrack_match_bundle_bridge_smoke
```

Require two halves, 40 requested frames, non-zero usable player entities, zero full-file loads, populated bridge players, and both reference-safety flags. Record exact observed counts in `docs/status/current.md` under the dataset-adaptation evidence, while leaving actual inference and labeled accuracy `unproven`.

- [x] **Step 3: Run focused verification and commit source**

Run:

```bash
PATH=/tmp/football-audit-fixes-venv/bin:$PATH python3 -m pytest -q \
  backend/tests/test_run_football_external_soccertrack_adapter_smoke_test.py \
  backend/tests/test_run_football_external_soccertrack_sample_fixture_materialization.py \
  backend/tests/test_run_football_external_soccertrack_match_bundle_bridge_smoke.py \
  backend/tests/test_external_soccertrack_product_route.py \
  backend/tests/test_run_football_external_soccertrack_product_route_smoke.py \
  backend/tests/test_operational_docs.py
git diff --check
git add backend/scripts/run_football_external_soccertrack_adapter_smoke_test.py \
  backend/scripts/run_football_external_soccertrack_match_bundle_bridge_smoke.py \
  backend/tests/test_run_football_external_soccertrack_adapter_smoke_test.py \
  backend/tests/test_run_football_external_soccertrack_match_bundle_bridge_smoke.py \
  backend/tests/test_external_soccertrack_product_route.py \
  docs/reports/2026-09-13-football-analysis-readiness.md docs/status/current.md \
  docs/superpowers/plans/2026-09-13-soccertrack-gsr-coordinate-adapter.md
git commit -m "feat: stream SoccerTrack GSR coordinate windows"
```

Expected: focused verification passes and ignored generated data is not committed.

### Task 4: Rebind and verify the changed release source

**Files:**
- Modify: `backend/release/v7.3.json`
- Replace: `backend/release/verification/v7.3-pre-cloud.json`
- Modify: `docs/status/current.md`
- Generated, untracked: `.verification/receipt.json`, `.verification/logs/*.log`

**Interfaces:**
- Consumes: the Task 3 source commit and existing five release artifacts.
- Produces: a fresh metadata-only release binding and pre-cloud evidence; no final evidence.

- [x] **Step 1: Bind the manifest and remove old pre-cloud evidence**

Set manifest `sourceCommit` to the Task 3 commit and `createdAt` to current RFC3339 UTC, validate with `write_release_manifest --artifact-root "$PWD"`, remove the old pre-cloud evidence, and commit only those two release paths.

- [x] **Step 2: Run the canonical verifier and publish evidence**

Run:

```bash
PATH=/tmp/football-audit-fixes-venv/bin:$PATH VERIFY_DAYTONA=0 ALLOW_DAYTONA_MUTATION=0 scripts/verify.sh
PATH=/tmp/football-audit-fixes-venv/bin:$PATH python3 -m backend.scripts.write_verification_evidence \
  --phase pre_cloud --output backend/release/verification/v7.3-pre-cloud.json
```

Expected: all local gates pass, provider mutation is skipped, and evidence has 12 passed gates plus one pending provider gate.

- [x] **Step 3: Publish status and validate preflight**

Update status with the new source/verification identities, commit the evidence and status, then run:

```bash
manifest_sha="$(sha256sum backend/release/v7.3.json | cut -d ' ' -f 1)"
source_commit="$(jq -r .sourceCommit backend/release/v7.3.json)"
PATH=/tmp/football-audit-fixes-venv/bin:$PATH python3 -m backend.release.preflight validate \
  --repo-root . \
  --manifest backend/release/v7.3.json \
  --evidence backend/release/verification/v7.3-pre-cloud.json \
  --mode build-only \
  --image-tag "v7.3-${source_commit}-${manifest_sha:0:12}"
```

Run the phase's focused tests again and require `git status --short` to show only `.verification/`.
