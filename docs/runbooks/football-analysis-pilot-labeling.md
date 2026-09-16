# Frozen football-analysis pilot labeling

This runbook defines the tool-neutral handoff for the 18 frozen annotation tasks in [`football_analysis_pilot_annotation_tasks.json`](../../backend/benchmark_suites/football_analysis_pilot_annotation_tasks.json). Labels must be created without viewing pipeline predictions. Use any video annotation tool, then convert its export to the JSON contract below.

## Isolation rule

- Do not use model-assisted pre-labels or pipeline output.
- Keep task-local track IDs stable across frames; they need not identify a real player beyond the task.
- Lock all 18 task files before opening held-out pipeline results or held-out reference labels.
- Validation labels may be used for tuning only after their files are locked. Held-out labels remain evaluation-only.

## Annotation clips

The 18 task-sized videos are under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_analysis_pilot_corpus_v1/annotation_clips/`. `annotation_clips_manifest_v1.json` records each clip's source identity, SHA-256, dimensions, frame rate and exact frame count. Every clip is 100 seconds at native source resolution; together they contain the frozen 58,491 frames (30 minutes) and occupy 3,709,457,465 bytes.

Clip frame zero maps to the task's `sourceStartFrame`. Convert zero-based clip-local indexes with `source frameId = sourceStartFrame + clip frame index`; labels must contain source frame IDs, not clip-local indexes. The clips contain no predictions or pre-labels.

Sample by **source-frame cadence**, not by taking every `evaluationFrameStep`th clip frame from clip zero or by resampling to a nominal output fps. The first required zero-based clip index is `(-sourceStartFrame) % evaluationFrameStep`; subsequent indexes add `evaluationFrameStep` until the task's `frameCount` is reached. For `belmont-melrose-2024-09-03-01`, clip frame 0 is source frame 39,478, but the first two labeled clip indexes are 2 and 8 (source frames 39,480 and 39,486). Thirteen of the 18 clips have a nonzero first-index offset. If an annotation tool numbers exported frames from 1, subtract 1 before this mapping. Keep the intact clip available between sampled frames for identity and event review.

## CVAT export handoff

Before annotation, sign in to the local CVAT account and confirm a real frame in the first validation job at `http://localhost:8080/tasks/13/jobs/13`; an HTTP 200 for the unauthenticated SPA is not a frame check. On 15 September the UI was stuck on “Connecting…” because host disk usage exceeded CVAT's default 90% health threshold, despite approximately 14 GiB free. The local Compose override now sets `CVAT_HEALTH_DISK_USAGE_MAX: '95'` for `cvat_server` only; this retains a 5% reserve and restored an all-working health response and login screen. Check actual free space with `df -h /` and CVAT health at `http://localhost:8080/api/server/health/?format=json` if the UI stalls again. Do not delete frozen clips or silently disable health checks. An authenticated job-frame render still needs reviewer confirmation.

A synthetic superuser browser session subsequently rendered validation job 13's sampled frames 0, 250 and 499 with intact football footage. That session was invalidated and removed without saving an annotation. The independent reviewer must still use their normal sign-in to confirm footage, ordinary permissions and the Save path before labeling; the superuser render does not count as a completed label.

A disposable three-frame validation probe subsequently passed normal non-admin browser sign-in, frame render, one synthetic rectangle Save and reload persistence; its assigned worker could export `CVAT for video 1.1` XML. The same worker received HTTP 403 for unassigned frozen task/job 13. Before pilot labeling, the admin must assign the relevant frozen jobs to a **named independent reviewer** with their own account; a shared generic account cannot support reviewer attestation. The probe task and account were removed, and none of its boxes is pilot truth.

The local CVAT v2.70.0 pilot at `http://localhost:8080/tasks` has 18 blank tasks named in manifest order. It reads the frozen clips from a read-only share, without reuploading video or using a GPU. Its task IDs are local setup details, not source-frame IDs. A separate two-frame format probe established that `CVAT for video 1.1` XML `<box frame="...">` values are **sampled clip-local frame numbers**: 2 and 8 for the first Belmont–Melrose task, not CVAT UI indexes 0 and 1. Convert an XML box with `source frameId = sourceStartFrame + XML box frame`; do not apply the first-frame offset or step again. A three-frame probe also exported its interpolated middle box explicitly at clip frame 8 with `keyframe="0"`; interpolation does not substitute for independent frame review. Both disposable probe tasks were removed after their XML was saved; neither is pilot truth.

Player, referee and visible-ball rectangles/tracks come from the CVAT export. Set each player rectangle's `team` attribute to `home`, `away` or `unknown`; leave no `__undefined__` defaults. CVAT track `0` becomes v3 `trackId` `cvat-0`, stable within that task. The converter rejects nonmanual track sources, unsupported annotations, unresolved teams, occluded ball boxes, off-cadence boxes, conflicting boxes and mismatched CVAT metadata. Export `CVAT for video 1.1` **without images**.

CVAT boxes alone cannot attest that a frame was fully checked, classify a ball with no box, mark possession, or review pass/shot intervals. Use the source-frame-accurate, deliberately incomplete sidecar templates under `backend/storage/football-analysis-pilot-cvat-v2.70.0/review-templates/`, or create a new one without overwriting an existing file:

```bash
python3 -m backend.scripts.convert_football_analysis_pilot_cvat_labels \
  --task-id TASK_ID --template-out backend/storage/football-analysis-pilot-cvat-v2.70.0/review-templates/TASK_ID.json
```

For every sidecar frame, set `reviewed: true` only after independent frame review, fill `ballVisibility` (`visible`, `occluded`, `not_visible` or `unknown`) and a v3 `possession` object, and keep `ballPitchPositionMeters`/`entityPitchPositionsMeters` null/empty unless an independent `pitchReference` supports them. A `visible` ball needs one CVAT box; a non-visible ball must have none. Possession `trackId`, when present, uses the `cvat-N` identity from the same frame. After reviewing the intact clip for all supported pass/shot intervals, set `eventsReviewed: true` and fill `events` with source-frame intervals, using `[]` only if review genuinely found none. The reviewer—not the converter—sets `annotatorId`, `independentAnnotation: true`, `pipelineOutputUsed: false` and a genuine UTC `lockedAt` after completion. Never fill these from predictions or unreviewed defaults.

Then convert the completed sidecar and image-free CVAT ZIP:

```bash
python3 -m backend.scripts.convert_football_analysis_pilot_cvat_labels \
  --task-id TASK_ID --export-zip CVAT_VIDEO_EXPORT.zip --review COMPLETED_SIDECAR.json
```

The command uses only the live repo's frozen task/clip manifests, verifies the local clip and parent source-video SHA-256 values, CVAT video metadata and every v3 field, then exclusively creates the task's declared `labelOutputPath` with mode 0600. An existing label is never overwritten. Incomplete review exits nonzero and writes no label. CVAT XML contains only the media basename, not a media hash: metadata checks cannot prove the export came from the hashed clip. The reviewer must confirm the CVAT task displayed the frozen shared clip before locking a sidecar. This is a format/integrity path, not an accuracy result.

## Label file contract

Write each task to its declared `labelOutputPath`. The root object contains exactly:

- `schemaVersion`: `football_analysis_pilot_labels_v3`
- `taskId` and `sourceVideoSha256`: exact values from the frozen task
- `independentAnnotation`: `true`
- `pipelineOutputUsed`: `false`
- `annotatorId`: a non-empty reviewer identifier
- `lockedAt`: genuine RFC3339 UTC timestamp ending in `Z`, not in the future
- `pitchReference`: `null`, or the independently sourced reference identity, SHA-256 and association method
- `frames`: one entry for every declared evaluation frame, in order; include source frame `frameId` exactly when `frameId % evaluationFrameStep == 0`
- `events`: supported pass and shot intervals inside the task

Keep one unambiguous value per JSON key. The converter, label audit and task scorer reject duplicate keys in reviewer sidecars and locked labels; a repeated `pipelineOutputUsed` or other attestation cannot be resolved by taking its last value.

Every frame has this shape:

```json
{
  "frameId": 10,
  "ball": {"visibility": "visible", "bbox": [40, 20, 42, 22], "pitchPositionMeters": null},
  "entities": [
    {"trackId": "home-7", "kind": "player", "team": "home", "bbox": [10, 5, 20, 30], "pitchPositionMeters": [30.0, 20.0]},
    {"trackId": "ref-1", "kind": "referee", "team": "unknown", "bbox": [50, 5, 60, 30], "pitchPositionMeters": null}
  ],
  "possession": {"state": "observed", "team": "home", "trackId": "home-7"}
}
```

Coordinates are source-video pixel `xyxy` values. Boxes must be finite, positive-area and inside the task's declared width and height. `pitchPositionMeters` is `null` unless a `pitchReference` identifies the independent source by ID, SHA-256 and either `predeclared_identity` or `withheld_control_keypoint` association. Ball visibility is `visible`, `occluded`, `not_visible`, or `unknown`; only `visible` has a box. Entity kind is `player` or `referee`, and team is `home`, `away`, or `unknown`. Possession state is `observed`, `inferred`, or `unknown`; an observed/inferred track must exist in the same frame, while unknown possession uses unknown team and a null track.

Events have this shape:

```json
{
  "eventId": "pass-1",
  "type": "pass",
  "startFrame": 10,
  "endFrameExclusive": 12,
  "team": "home"
}
```

Event type is `pass` or `shot`; the interval must be wholly inside the task.

## Completion gate

Run:

```bash
python3 -m backend.scripts.validate_football_analysis_pilot_labels
```

Exit zero means all 9,297 declared evaluation frames across all 18 tasks are present, valid and locked. The intact clips still cover 58,491 source frames and 30 minutes; unsampled frames are not part of the label payload. Missing, partial, off-cadence, malformed, prediction-assisted, mismatched-source or out-of-bounds labels exit nonzero and contribute zero completed minutes. Do not edit the task manifest to make this gate pass.

This is a label-integrity gate, not the accuracy evaluator. Scoring protocol v3 is frozen inside the corpus inventory before annotation: it fixes evaluation-frame cadence and identity, ball/player association and IoU, event one-to-one matching, team mapping, possession transitions at the evaluation cadence, zero-denominator handling, confidence intervals, per-source acceptance and pitch-reference restrictions. The tested scoring core and exact-commit TrackEval adapter cover the declared metrics. Once a task is independently labeled and its pipeline run is complete, score its native artifacts with:

```bash
python3 -m backend.scripts.evaluate_football_analysis_pilot task \
  --task-id TASK_ID \
  --artifact-dir backend/storage/MATCH_STORAGE/matches/MATCH_ID \
  --prediction-scope task-interval \
  --trackeval-root /path/to/pinned/TrackEval \
  --source-declaration TEAM_DECLARATION.json > TASK_RESULT.json
```

`--prediction-scope task-interval` adds the frozen physical-video frame offset; use `whole-source` only when the artifacts retain original whole-video frame IDs. Keep each JSON result, then pool exactly the three frozen tasks for one source.

Before viewing any pipeline output—and before invoking a held-out worker—the independent reviewer must preserve one separate, prediction-free declaration per source. Its exact JSON fields are `schemaVersion: "football_analysis_pilot_source_declaration_v1"`, `sourceId`, `myTeamSide: "home"` or `"away"`, non-empty `reviewerId`, genuine RFC3339 UTC `declaredAt`, non-empty `footageBasis`, `independentDeclaration: true` and `pipelineOutputUsed: false`. Keep its original bytes and SHA-256 beside the review sidecars; do not add fields to the frozen v3 label payload. Pass the same file to all three task commands and the source command. The scorer reads it before task predictions, derives the team mapping from it, records its hash in each task result and rejects changed/mixed hashes when pooling. Numeric `myTeamCluster` IDs are task-local, not home/away names; do not reuse an ID across clips or pick a side from cluster benchmark scores. The file's self-attestation and timestamp do **not** prove that the reviewer was blind or that the file existed before held-out inference; independent reviewer attestation and retained creation evidence remain necessary for pilot acceptance. Prior validation cluster summaries have been inspected during engineering work and must not be shown to the independent annotator.

The native pipeline samples clip-local frames `0, step, 2×step, ...`, while scoring protocol v3 selects source frames divisible by `evaluationFrameStep`. For 13 / 18 frozen tasks, `sourceStartFrame` is off that grid; running their unchanged annotation clip through the worker would produce **zero exact scored-frame overlap**. The evaluator rejects such task-interval artifacts unless the mathematically aligned source start is supplied. Do not change the frozen annotation clip or shift prediction IDs onto different images. Before any held-out inference, use the prepared separate inference video containing real source frames from `alignedStart = sourceStartFrame - sourceStartFrame % evaluationFrameStep` through `sourceEndFrameExclusive`; verify its parent and clip hashes and the three correspondence anchors against the aligned-media manifest. Run the worker on that aligned clip only **after** independent labels are locked, then add `--prediction-source-start-frame alignedStart` to the task scoring command. Omit that flag for aligned tasks and `whole-source` artifacts. For every held-out task, also pass `--expected-input-video-sha256 SHA256`: use the aligned clip hash in `aligned_media_manifest_v1.tsv` for off-grid tasks and the frozen annotation-clip hash for the on-grid task. New sealed-worker imports persist `input_video_identity.json` transactionally from the validated job receipt. The task CLI checks the frozen task and local clip manifests, hashes the selected clip bytes and rejects a missing, mistyped or mismatched identity; the source CLI rechecks each held-out task-result hash and aligned start. Keep the sealed job receipt as separate provenance, since a local identity file is not a signature against later tampering. Older validation artifacts have no identity file and remain input-hash-unbound. The candidate `belmont-melrose-2024-09-03-01` aligned clip starts four real source frames earlier (39,474 instead of 39,478), contains 3,004 frames, and passed three correspondence checks; its private hash-bound probe is under `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_analysis_pilot_corpus_v1/inference_clips/`. It has **not** been sent to the worker or scored.

The source declaration names a **semantic side**; it does not set any saved match's task-local `myTeamCluster`. After the independent labels and declaration are locked (and, for held-out tasks, after the authorized worker import), a separate operator must use the normal match workspace to choose the cluster corresponding to that declared side for **each** match from its footage and jersey-color swatches, not from locked labels, official `teamId` joins or benchmark-selected-cluster scores. The workspace calls `PATCH /api/matches/{MATCH_ID}/config` with `{"myTeamCluster": TASK_LOCAL_ID}`; the existing route validates that ID, reuses saved raw rows, and transactionally reprocesses frames, analytics, events and accepted match state. Preserve each task ID, match ID, selected local ID, the declaration SHA-256, the config response and before/after artifact hashes before scoring the **reprocessed** artifacts. Never copy one numeric cluster ID to the other two clips: the validation `117093` clusters reverse their official-team correspondence between task `01` and tasks `02/03`. If the footage does not support an unambiguous choice, keep `requiresTeamSelection=true` and report team, possession and event acceptance as unproven; do not use the validation oracle to fill the gap. This post-lock operator choice does not retroactively make the earlier blind declaration or labels prediction-assisted.

Before that PATCH, confirm the app is serving the **pilot** storage root containing the declared `MATCH_ID` (the validation imports live under `backend/storage/football-analysis-pilot-predictions-v1/`), and inspect the match ID/source in a read-only GET. The default product app may serve a different storage root; do not update a similarly named saved match there. Verify the scored artifact directory is the same instance that received the selection and reprocessing.

For the separate local pilot operator workspace, start these two processes from the repository root in separate terminals. The product app/UI on 8000/5173 and CVAT on 8080 stay untouched. The pilot API serves the existing validation-import storage root on 8001, while the optional dev proxy makes that API available to the normal React UI on 5174:

```bash
GUERILLA_STORAGE_ROOT=backend/storage/football-analysis-pilot-predictions-v1 \
  PROCESSING_BACKEND=local \
  TRUSTED_FRONTEND_ORIGINS='http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174' \
  python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
```

```bash
PILOT_API_TARGET=http://127.0.0.1:8001 \
  npm --prefix frontend run dev -- --host 127.0.0.1 --port 5174
```

Check `GET http://127.0.0.1:5174/api/matches/{MATCH_ID}` against the exact expected pilot match before later team selection. This workspace displays saved predictions, so the independent annotator must use CVAT's prediction-free jobs instead; opening 5174 is for the post-lock footage-only team operator. Do not choose a cluster yet. The local 15 September UI check proved one validation match's video and unresolved-team controls, not the human declaration or label gate.

For an off-grid held-out task, use this form after the label lock (the on-grid task omits the start flag and uses its annotation-clip hash):

```bash
python3 -m backend.scripts.evaluate_football_analysis_pilot task \
  --task-id TASK_ID --artifact-dir backend/storage/MATCH_STORAGE/matches/MATCH_ID \
  --prediction-scope task-interval --prediction-source-start-frame ALIGNED_START \
  --expected-input-video-sha256 ALIGNED_CLIP_SHA256 \
  --trackeval-root /path/to/pinned/TrackEval \
  --source-declaration TEAM_DECLARATION.json > TASK_RESULT.json
```

```bash
python3 -m backend.scripts.evaluate_football_analysis_pilot source \
  --source-id SOURCE_ID \
  --source-declaration TEAM_DECLARATION.json \
  --task-result TASK_01_RESULT.json \
  --task-result TASK_02_RESULT.json \
  --task-result TASK_03_RESULT.json > SOURCE_RESULT.json
```

The source command rejects missing, duplicate, cross-source or impossible task results and requires every task to carry the same declared team mapping. It namespaces frames by task rather than merging half-local frame numbers, retains each task's prediction scope, start and input hash alongside task-stratified player/tracking/possession metrics, pools ball/event denominators and pitch-error samples, recalculates confidence intervals, and applies every frozen acceptance bar. A real label-versus-prediction run is still required before producing any pilot result. Label completeness alone is never accuracy evidence.

Every saved task result must retain its complete ball, event and pitch counters, event false-positive/false-negative counts and pitch-eligibility flag. Pooling rejects missing fields, inconsistent event/ball arithmetic, and observed/inferred/unknown ball-source totals that do not equal the prediction count; it also rejects duplicate JSON keys. Saved task-result JSON is local, unsigned evidence, not proof that its metrics came from the retained labels and prediction artifacts. Preserve those inputs and rerun the task scorer before treating a source result as analyst acceptance.

## Ready validation artifacts

The 11 off-grid held-out `TASK_ID-aligned.mp4` files are now available in `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_analysis_pilot_corpus_v1/inference_clips/`. The local `aligned_media_manifest_v1.tsv` there binds parent, annotation and aligned video hashes, aligned source starts, prefix/frame counts and three-anchor comparison bounds. All 11 matched their frozen media and frame-count contracts; none has been sent to the worker or scored. The two other off-grid tasks are `117092` validation windows with existing whole-source artifacts, so they need no extra inference clip. Keep the independent-label lock and expected input-video hash check above before using any held-out result.

Do not open these before locking the independent labels. Once locked, use the following `--artifact-dir` values with `--prediction-scope task-interval` for `117093`:

- `soccertrack-v2-117093-01`: `backend/storage/football-analysis-pilot-predictions-v1/matches/dd7c1e792cae4d46bf452e079ca461d5`
- `soccertrack-v2-117093-02`: `backend/storage/football-analysis-pilot-predictions-v1/matches/dda6be8971a34f9f841008dca7ced4c4`
- `soccertrack-v2-117093-03`: `backend/storage/football-analysis-pilot-predictions-v1/matches/a49358f5360348a7b7135d90abb85dab`

For `117092`, use the intact-half artifact containing each frozen interval with `--prediction-scope whole-source`: first half `backend/storage/daytona-g-capacity-v7.3/matches/c43b571fdb1745a08b8209430bb65abe`, second half `backend/storage/daytona-g-capacity-v7.3/matches/5b56cbd876664b9b9fe25b1c95515b8f`. The evaluator applies the task window; do not rerun or recut these predictions.
