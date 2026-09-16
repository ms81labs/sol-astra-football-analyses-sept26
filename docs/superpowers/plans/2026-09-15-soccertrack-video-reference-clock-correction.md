# SoccerTrack video/reference clock correction implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. No subagents: the user requested autonomous inline execution.

**Goal:** Score validation predictions against the GSR/BAS instant corresponding to each frozen source-video frame, without changing pilot clips, annotation frames, model inference, or held-out isolation.

**Architecture:** The task manifest's `globalStartSeconds` is a concatenated-video clock. SoccerTrack metadata's `SECOND_HALF.matchTimeStart` is an independent tracker clock: `117092` starts at 2700 s after a 2695 s first video; `117093` starts at 2699.967 s after a 2705 s first video. Derive one offset per task from the task's video-segment start and metadata period anchor, then reuse that mapping in bounded GSR extraction, pitch selection and BAS event truth. Keep the old reference extracts recoverable.

**Tech Stack:** Python 3.12, standard-library XML/JSON/gzip, NumPy/OpenCV for existing pitch scoring, pytest, Git release verifier.

**Spec:** [2026-09-13 football analysis readiness](../../reports/2026-09-13-football-analysis-readiness.md), frozen [annotation tasks](../../../backend/benchmark_suites/football_analysis_pilot_annotation_tasks.json), and the source-bound SoccerTrack period metadata listed in the pilot corpus.

## Global constraints

- `117092` and `117093` are validation-only. Do not open `118575` or other held-out references, or run held-out inference.
- Keep all 18 selected video intervals, 9,297 evaluation frames, 30-minute denominator, source hashes, and saved predictions unchanged.
- Reference labels may select and score post-inference windows; they must not center crops, seed detections or change runtime options.
- Preserve old ignored reference extracts and summaries by an exact-name move before writing replacements.
- A local verifier pass is engineering evidence, not football accuracy; the independent manual-label gate remains separate.

---

### Task 1: Derive the shared video-to-reference offset

**Files:**
- Modify: `backend/scripts/materialize_football_analysis_pilot_reference_intervals.py`
- Test: `backend/tests/test_materialize_football_analysis_pilot_reference_intervals.py`

**Interface:** `reference_clock_offsets(tasks: list[dict], video_paths: list[str], metadata_xml: Path) -> dict[str, float]` maps task ID to `SECOND_HALF.matchTimeStart / 1000 - (globalStartSeconds - localStartSeconds)` for the second video, or `0.0` for the first. Reject an unknown video path, a missing/nonfinite second anchor, and a source with other than two ordered half videos.

- [x] Add a synthetic test with first-video length 10 s, second tracker anchor 8 s, two task videos and expected offsets `0.0` and `-2.0`; run `python3 -m pytest -q backend/tests/test_materialize_football_analysis_pilot_reference_intervals.py` and observe the expected red failure.
- [x] Implement the helper using `xml.etree.ElementTree.parse(metadata_xml).findall('.//period')`, the frozen task fields and ordered video paths; run the focused test to green.
- [x] Check the real validation offsets from metadata: `117092` second is `+5.0`, `117093` second is `-5.033`; first halves are `0.0`. Bind the metadata file hashes in later artifacts.

### Task 2: Materialize corrected GSR windows without changing video tasks

**Files:**
- Modify: `backend/scripts/materialize_football_analysis_pilot_reference_intervals.py`
- Test: `backend/tests/test_materialize_football_analysis_pilot_reference_intervals.py`
- Replace recoverably: the two ignored `pilot_reference_intervals.jsonl.gz` files and summaries under `.../soccertrack/{117092,117093}/`.

**Interface:** Add optional `reference_clock_offsets_seconds: list[float] | None` to `materialize_reference_intervals`. For video interval `[start,end)` with offset `d`, select tracker `[start+d,end+d)` and write both `matchTimeSeconds` and `videoTimelineSeconds = matchTimeSeconds-d` for each row. Default offsets are zero for existing callers. Return the video intervals, corrected tracker intervals, offsets, counts and hashes. CLI obtains task offsets from Task 1 instead of treating `selectedIntervalsBySource` as tracker-clock windows.

- [x] Add a fixture in which the second task video's `[10,11)` maps to tracker `[8,9)`; assert the selected frame and its `videoTimelineSeconds` are correct. Run red.
- [x] Implement selection and CLI mapping; run focused test green. Reject offset-count mismatch, overlap, nonfinite offsets and task/interval mismatch; the exact-millisecond end-boundary regression was red and is now green.
- [x] Move the two old ignored outputs/summaries to exact `.pre_video_clock` names after checking those archive names do not exist. Run the corrected CLI for `117092` and `117093` using only their existing tracker/metadata XML. Confirm 7,500 video-task frames per source, exact 600 s selected video duration, zero malformed locations, and first/second offset summaries.

### Task 3: Rebind pitch and resolution diagnostics to video time

**Files:**
- Modify: `backend/scripts/evaluate_football_analysis_pilot_soccertrack_pitch.py`
- Modify: `backend/scripts/evaluate_football_analysis_pilot_soccertrack_resolution.py`
- Modify: `backend/benchmark_suites/football_analysis_pilot_soccertrack_pitch_diagnostic.json`
- Modify: `backend/benchmark_suites/football_analysis_pilot_soccertrack_resolution_diagnostic.json`
- Test: `backend/tests/test_run_football_external_soccertrack_calibrated_alignment.py`

- [x] Add a small fixture proving reference selection uses `videoTimelineSeconds`; a missing field fails closed through direct indexed access. Run red.
- [x] Change both mains to select the frozen task window by `videoTimelineSeconds`, not `matchTimeSeconds`. Keep frame-local scoring, the loose 5 m association threshold, all model/camera hashes, and `referenceLabelsUsedForInference=false`.
- [x] Re-run both diagnostic CLIs; verify each corrected `117093` task still has exactly 2,500 reference frames, and report new matched counts, precision/recall, median/p95 per task and the frozen 550-reference 25-frame samples. Do not promote runtime calibration or tiling.

### Task 4: Fix BAS event truth on the same reference clock

**Files:**
- Modify: `backend/scripts/evaluate_football_analysis_pilot_soccertrack_events.py`
- Modify: `backend/benchmark_suites/football_analysis_pilot_soccertrack_event_diagnostic.json`
- Test: `backend/tests/test_evaluate_football_analysis_pilot_soccertrack_events.py`

**Interface:** `build_event_truth(task, actions, *, reference_clock_offset_seconds: float = 0.0)` selects BAS seconds within `[globalStart+d,globalEnd+d)` and writes source frame `round((seconds-(globalStart-localStart+d))*fps)`.

- [x] Add a second-video fixture with video segment start 10 s, BAS period anchor 8 s, a two-second video task, an action at 9 s and expected local source frame 25; run red.
- [x] Implement the one-offset correction and call Task 1's helper from the diagnostic main for `117092`; bind metadata XML hash and task offsets in the event artifact. Run focused test green.
- [x] Re-run the event diagnostic; disclose any changed matched counts, class denominators and confidence intervals. Current-code unsupported passes remain suppressed, not relabeled as correct.

### Task 5: Refresh provenance, report and release receipt

**Files:**
- Modify: `backend/benchmark_suites/football_analysis_pilot_corpus.json`
- Modify: `backend/benchmark_suites/football_analysis_pilot_annotation_tasks.json` only for its inventory hash; task intervals/frames must compare equal to the archived prior manifest.
- Modify ignored: `annotation_clips/annotation_clips_manifest_v1.json` only for `taskManifestSha256`; every entry and clip hash remains unchanged.
- Modify: `docs/reports/2026-09-13-football-analysis-readiness.md`
- Modify: `docs/status/current.md`
- Modify: `backend/release/v7.3.json`, `backend/release/verification/v7.3-pre-cloud.json`

- [x] Update the pilot inventory's corrected reference hashes/counts and diagnostic summaries. Keep the old tracked task manifest recoverable in Git history; compare `.tasks` byte-for-byte against HEAD and update only the inventory hash. Repair the previously stale ignored clip-manifest pointer after that comparison.
- [x] Correct every superseded second-half/pool/event claim in the readiness report and status. Preserve engineering-versus-accuracy separation, held-out exclusion, source split and denominators.
- [ ] Commit source, then validated manifest metadata. Run `./scripts/verify.sh` with provider mutation disabled, inspect the exact receipt and write pre-cloud evidence. Commit evidence/status and run build-only preflight with the immutable tag computed from the exact source commit and first 12 manifest digest characters, followed by focused release tests.
- [ ] Run the fail-closed manual-label validator and read-only Daytona listing. Leave the retained CPU staging sandbox open; do not launch a GPU job or open held-out source labels.
