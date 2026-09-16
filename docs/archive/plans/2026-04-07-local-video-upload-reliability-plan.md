# Local Video Upload Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the local video upload -> processing -> review path honest, debuggable, and test-proven for the 1-minute real clip workflow.

**Architecture:** Introduce an explicit unresolved-player contract instead of silently forcing team labels, gate tactical interpretation on truth prerequisites, and surface upload/job failures clearly through the existing local job system. Keep the current local-first pipeline intact; no cloud worker work in this plan.

**Tech Stack:** FastAPI, Pydantic, SQLite/JSON artifact storage, Python pytest, React, TypeScript, Vitest.

## Current Status

- Team-label honesty is restored:
  - unresolved video matches keep players in a neutral `unassignedPlayers` bucket
  - no silent fallback to `team_clusters[0]`
- Tactical interpretation gating is live:
  - unresolved-team and untrusted-ball states pause tactical surfaces instead of pretending readiness
- API harness is stabilized for the local upload path:
  - `backend/tests/test_api.py` now runs under async `httpx.AsyncClient + ASGITransport`
  - core routes used by the harness were converted to `async def`
- Inline jobs now use the same failure-reporting path as worker jobs
- Verified backend slice:
  - `PYTHONPATH=. python3 -m pytest backend/tests/test_processor.py backend/tests/test_video_pipeline.py backend/tests/test_worker.py backend/tests/test_jobs.py backend/tests/test_api.py -q`
  - result: `41 passed`
- Verified frontend slice:
  - `npm test -- --run src/utils/uploadErrors.test.ts src/components/StatsPanel.test.tsx src/components/TeamSelectionBanner.test.tsx`
  - result: `7 passed`
  - `npm run build` passed
- Live 1-minute clip repro is complete:
  - clip: `/root/WorkSpace/fotball-analyst/.worktrees/videos/trimed-football-2-1minute.mp4`
  - result: upload succeeds, job fails honestly on auto-homography miss, and the UI now tells the operator to disable auto-detect and enter manual pitch corners
  - operator recovery path is now live:
    - calibration panel shows `Auto-detect missed the pitch`
    - `Switch to manual calibration` flips the upload UI into manual mode
    - ordered inputs for `Top Left`, `Top Right`, `Bottom Right`, `Bottom Left` appear immediately, plus a `Reset points` action
    - manual mode now includes a first-frame preview picker that fills the next empty corner when the operator clicks the video frame
    - manual mode now includes `Retry last video with current calibration`, so the failed clip can be resubmitted without reopening the file chooser
- Local tracker dependency compatibility is restored:
  - repo-root `lap.py` shim satisfies Ultralytics' `lap` import in externally managed Python environments
  - verified with `PYTHONPATH=. python3 -m pytest backend/tests/test_lap_shim.py -q`
- Live manual retry is now proven past the previous dependency wall:
  - after setting manual points, retrying the 1-minute clip enters real `Processing match...`
  - backend worker log confirms YOLO/BoT-SORT frame processing is underway instead of failing immediately on `No module named 'lap'`
- Manual-calibrated local completion proof is now real:
  - inline proof job: `c04b728f765644fe91a188cfdb5bb24a`
  - proof match: `e4795c0bf5274072851cc6478cb0dd2d`
  - terminal job metadata is now persisted:
    - `startedAt`
    - `completedAt`
    - `durationSeconds`
    - `logPath`
  - verified proof result:
    - `jobStatus: completed`
    - `matchStatus: ready`
    - `durationSeconds: 117.840114`
    - `frameCount: 124`
    - `withBallFrames: 0`
    - `eventCount: 0`
    - artifacts written: `frames.json`, `analytics.json`, `events.json`, `raw_rows.json`
  - important caveat:
    - the proof run used direct inline `run_job(...)`, so the persisted `logPath` is correct metadata but the file itself is not created on disk
    - physical log-file existence remains proven by the spawned/API path, for example `job_3ab8de59118b47508a8e617d83ea2f95.log`

## Remaining Gap

The local reliability lane is now complete enough to hand off. The live blocker is no longer hidden failure, test harness drift, or the `lap` dependency wall. The current real blocker is product reality:

- auto-homography does not detect the pitch on the 1-minute trimmed clip in headless/server mode
- the manual recovery path now truly runs and has one full completion proof on this clip, but the resulting workspace is still weak (`withBallFrames: 0`, `eventCount: 0`, `requiresTeamSelection: true`)
- the next substantive lane is either:
  - script and freeze the trimmed-clip benchmark / GPU handoff contract, or
  - strengthen automatic pitch detection on real footage so manual fallback is needed less often

---

## File Map

### Backend

- Modify: `backend/app/schemas.py`
- Modify: `backend/app/analytics.py`
- Modify: `backend/app/processor.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/jobs.py`
- Modify: `backend/app/worker.py`
- Modify: `backend/app/storage.py` only if schema persistence needs a companion change
- Modify: `backend/app/video_pipeline.py`

### Frontend

- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/TacticalPitch.tsx`
- Modify: `frontend/src/components/StatsPanel.tsx`
- Modify: `frontend/src/components/TeamSelectionBanner.tsx`
- Modify: `frontend/src/utils/api.ts`

### Tests

- Modify: `backend/tests/test_processor.py`
- Modify: `backend/tests/test_video_pipeline.py`
- Modify: `backend/tests/test_api.py`
- Modify: `backend/tests/test_jobs.py`
- Modify: `backend/tests/test_worker.py`
- Modify: `frontend/src/components/StatsPanel.test.tsx`
- Modify: `frontend/src/components/TeamSelectionBanner.test.tsx`
- Modify: `frontend/src/utils/uploadConfig.test.ts`

### Docs

- Modify: `README.md`
- Modify: `SESSION-HANDOFF.md`
- Modify: `REVIEW-FINDINGS.md` only if findings are explicitly closed

---

## Task 1: Restore Team-Label Honesty Without Losing Player Visibility

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/analytics.py`
- Modify: `backend/app/processor.py`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/components/TacticalPitch.tsx`
- Test: `backend/tests/test_processor.py`

- [ ] **Step 1: Write the failing backend test for unresolved cluster behavior**

Add a processor test asserting that unresolved team selection does not auto-pick the first cluster and that players remain visible in a neutral bucket.

```python
def test_prepare_video_outputs_keeps_players_unassigned_until_team_selected():
    config = MatchConfig()
    video_result = {
        "rows": [
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 4, "X": 40.0, "Y": 50.0},
            {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "player", "Track_ID": 12, "X": 60.0, "Y": 50.0},
        ],
        "trackColors": {
            "4": [[20, 90, 220]],
            "12": [[220, 50, 60]],
        },
    }

    frames, clusters, requires_team_selection, _raw = _prepare_video_outputs(video_result, config)

    assert requires_team_selection is True
    assert len(clusters) == 2
    assert frames[0].myTeam == []
    assert frames[0].enemies == []
    assert [player.id for player in frames[0].unassignedPlayers] == [4, 12]
```

- [ ] **Step 2: Run the targeted processor test and confirm failure**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=. python3 -m pytest backend/tests/test_processor.py -q
```

Expected: FAIL because `FrameData` has no `unassignedPlayers` and processor still auto-selects the first cluster.

- [ ] **Step 3: Add the neutral player bucket to backend and frontend types**

Update schemas so unresolved players survive normalization without being mislabeled.

```python
class FrameData(BaseModel):
    frameId: int
    timestamp: float
    ball: BallData | None = None
    myTeam: list[PlayerData] = Field(default_factory=list)
    enemies: list[PlayerData] = Field(default_factory=list)
    unassignedPlayers: list[PlayerData] = Field(default_factory=list)
    possession: "BallOwnership | None" = None
```

```ts
export interface FrameData {
  frameId: number;
  timestamp: number;
  ball: BallData | null;
  myTeam: PlayerData[];
  enemies: PlayerData[];
  unassignedPlayers: PlayerData[];
  possession?: BallOwnership | null;
}
```

- [ ] **Step 4: Stop auto-selecting the first team cluster**

Change the processor so unresolved team selection remains unresolved.

```python
def _resolve_selected_cluster(config: MatchConfig, team_clusters: list[ColorClusterSummary]) -> tuple[int | None, bool]:
    if not team_clusters:
        return None, False
    if config.myTeamCluster is not None:
        return config.myTeamCluster, False
    return None, True
```

```python
def _classify_video_rows(rows: list[dict], config: MatchConfig, team_clusters: list[ColorClusterSummary]) -> tuple[list[dict], bool]:
    selected_cluster, requires_team_selection = _resolve_selected_cluster(config, team_clusters)
    if not team_clusters:
        return [dict(row) for row in rows], False

    if selected_cluster is None:
        return [dict(row) for row in rows], True

    cluster_result = cluster_result_from_summaries(team_clusters)
    return classify_player_rows_by_cluster(rows, cluster_result, selected_cluster), False
```

- [ ] **Step 5: Preserve raw `"player"` entities during normalization**

Update normalization so neutral players are kept visible.

```python
elif entity_type == "player":
    frame.unassignedPlayers.append(
        PlayerData(
            id=int(row["Track_ID"]),
            x=float(row["X"]),
            y=float(row["Y"]),
            confidence=confidence,
        )
    )
```

- [ ] **Step 6: Render unresolved players in the tactical pitch**

In `TacticalPitch.tsx`, draw `unassignedPlayers` in a neutral style so operators can still review tracking before choosing a team.

```tsx
const unassigned = frame?.unassignedPlayers ?? [];
unassigned.forEach((player) => {
  drawPlayer(ctx, player.x, player.y, {
    fill: '#94a3b8',
    stroke: '#e2e8f0',
    label: `#${player.id}`,
  });
});
```

- [ ] **Step 7: Re-run targeted tests**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=. python3 -m pytest backend/tests/test_processor.py -q
```

Expected: PASS

---

## Task 2: Gate Tactical Interpretation When Truth Prerequisites Are Missing

**Files:**
- Modify: `frontend/src/components/StatsPanel.tsx`
- Modify: `frontend/src/components/TeamSelectionBanner.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/components/StatsPanel.test.tsx`
- Test: `frontend/src/components/TeamSelectionBanner.test.tsx`

- [ ] **Step 1: Write the failing stats gating test**

Add a test proving that untrusted-ball runs hide tactical/stat surfaces.

```tsx
it('hides tactical stat surfaces when ball signal is untrusted', () => {
  render(
    <StatsPanel
      stats={{ ...baseStats, ballSignalStatus: 'untrusted', ballSignalMessage: 'ball track lost' }}
      shotSummary={shotSummary}
      playerProfiles={sampleProfiles}
    />
  );

  expect(screen.getByText('Ball signal untrusted')).toBeTruthy();
  expect(screen.queryByText('Possession')).toBeNull();
  expect(screen.queryByText('Pressing')).toBeNull();
  expect(screen.queryByText('Top Creator')).toBeNull();
});
```

- [ ] **Step 2: Write the failing unresolved-team guidance test**

Add a banner test making the unresolved state explicit.

```tsx
it('tells the operator that tactical interpretation is paused until a team is selected', () => {
  render(<TeamSelectionBanner clusters={sampleClusters} isSubmitting={false} onSelectCluster={() => {}} />);

  expect(screen.getByText(/tactical interpretation is paused/i)).toBeTruthy();
});
```

- [ ] **Step 3: Run the targeted frontend tests and confirm failure**

Run:

```bash
cd /root/WorkSpace/fotball-analyst/frontend
npm test -- --run src/components/StatsPanel.test.tsx src/components/TeamSelectionBanner.test.tsx
```

Expected: FAIL because the warning banner exists but the tactical sections still render.

- [ ] **Step 4: Gate stats and tactical highlights in the UI**

Add explicit gating in `StatsPanel.tsx`.

```tsx
const tacticalBlocked = stats.ballSignalStatus === 'untrusted';

if (tacticalBlocked) {
  return (
    <div className="w-full max-w-4xl mt-4 space-y-3">
      <div className="flex items-start gap-3 rounded-lg border border-amber-600/60 bg-amber-900/30 p-3">
        <span className="text-amber-400 text-lg leading-none mt-0.5">⚠️</span>
        <div>
          <p className="text-sm font-semibold text-amber-300">Ball signal untrusted</p>
          <p className="text-xs text-amber-400/80 mt-0.5">
            Tracking review is still available, but tactical stats are paused for this run.
          </p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Strengthen the unresolved-team banner copy**

Update the banner text so it matches the backend truth.

```tsx
<p className="text-xs text-amber-100/80">
  Pick which detected cluster belongs to your team. Tracking remains visible, but tactical interpretation is paused
  until you choose a team cluster.
</p>
```

- [ ] **Step 6: Prevent analysis affordances from implying readiness**

In `App.tsx`, disable or hide coach-facing analysis actions when `activeMatch.detail.requiresTeamSelection` is true or when `activeMatch.stats.ballSignalStatus === 'untrusted'`.

```tsx
const tacticalReady =
  !!activeMatch &&
  !activeMatch.detail.requiresTeamSelection &&
  activeMatch.stats.ballSignalStatus !== 'untrusted';
```

- [ ] **Step 7: Re-run targeted frontend verification**

Run:

```bash
cd /root/WorkSpace/fotball-analyst/frontend
npm test -- --run src/components/StatsPanel.test.tsx src/components/TeamSelectionBanner.test.tsx
npm run build
```

Expected: PASS

---

## Task 3: Make Auto-Homography Failure Actionable

**Files:**
- Modify: `backend/app/video_pipeline.py`
- Modify: `backend/app/worker.py`
- Modify: `backend/app/jobs.py`
- Modify: `frontend/src/utils/api.ts`
- Test: `backend/tests/test_video_pipeline.py`
- Test: `backend/tests/test_worker.py`

- [ ] **Step 1: Write the failing backend test for headless auto-homography failure messaging**

```python
def test_process_video_input_surfaces_actionable_auto_homography_failure(monkeypatch):
    config = MatchConfig(autoHomography=True)

    def fake_process(*args, **kwargs):
        raise RuntimeError("Homography could not be detected automatically. Please provide manualHomographyPoints.")

    monkeypatch.setattr("backend.app.video_pipeline._process_video_impl", fake_process)

    with pytest.raises(RuntimeError, match="manualHomographyPoints"):
        process_video_input(Path("/fake/video.mp4"), config)
```

- [ ] **Step 2: Run targeted backend tests and confirm failure if messaging is weak**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=. python3 -m pytest backend/tests/test_video_pipeline.py backend/tests/test_worker.py -q
```

- [ ] **Step 3: Normalize auto-homography failure into a stable operator-facing error**

Wrap the video pipeline call with a friendlier error boundary.

```python
try:
    result = _process_video_impl(
        str(video_path),
        output_parquet=None,
        homography_points=homography_points,
        return_rows=True,
        auto_homography=auto_homography,
    )
except RuntimeError as exc:
    message = str(exc)
    if config.autoHomography and "manualHomographyPoints" in message:
        raise RuntimeError(
            "Automatic pitch detection failed for this clip in headless mode. "
            "Retry with 4 manual homography points."
        ) from exc
    raise
```

- [ ] **Step 4: Preserve failed job logs and surface the error cleanly**

In `worker.py`, keep the failed-job error message compact and operator-readable.

```python
except Exception as exc:
    error_message = str(exc)
    storage.update_job(
        job_id,
        status="failed",
        progress=1.0,
        message="Processing failed",
        error=error_message,
    )
```

- [ ] **Step 5: Make polling failures show the backend job error directly**

Ensure the frontend propagates the stored backend message unchanged.

```ts
if (job.status === 'failed') {
  throw new Error(job.error || job.message || 'Processing job failed.');
}
```

- [ ] **Step 6: Re-run targeted backend verification**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=. python3 -m pytest backend/tests/test_video_pipeline.py backend/tests/test_worker.py -q
```

Expected: PASS

---

## Task 4: Stabilize the API Test Harness Around the Real Upload Path

**Files:**
- Modify: `backend/tests/test_api.py`
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Isolate the hanging API tests**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
timeout 20s env PYTHONPATH=. python3 -m pytest backend/tests/test_api.py -q
```

Expected: currently times out or stalls

- [ ] **Step 2: Convert the upload-path API tests to a stable async transport if needed**

If `TestClient` remains the stall source, rewrite the video upload lifecycle tests to use `httpx.AsyncClient` + `ASGITransport`.

```python
transport = httpx.ASGITransport(app=app)
async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
    response = await client.post("/api/matches", data=..., files=...)
```

- [ ] **Step 3: Add one dedicated video upload honesty test**

Assert that unresolved team selection keeps players visible but unassigned.

```python
assert detail_payload["requiresTeamSelection"] is True
frames_payload = (await client.get(f"/api/matches/{match_id}/frames")).json()
assert frames_payload["frames"][0]["myTeam"] == []
assert frames_payload["frames"][0]["enemies"] == []
assert len(frames_payload["frames"][0]["unassignedPlayers"]) >= 1
```

- [ ] **Step 4: Re-run the API slice**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=. python3 -m pytest backend/tests/test_api.py -q
```

Expected: PASS without hanging

---

## Task 5: Re-Prove the Actual Local Upload/Review Contract

**Files:**
- Modify only if truth changes: `README.md`
- Modify only if truth changes: `SESSION-HANDOFF.md`
- Modify only if findings close: `REVIEW-FINDINGS.md`

- [ ] **Step 1: Run the focused backend test suite**

Run:

```bash
cd /root/WorkSpace/fotball-analyst
PYTHONPATH=. python3 -m pytest \
  backend/tests/test_processor.py \
  backend/tests/test_video_pipeline.py \
  backend/tests/test_trust_crops.py \
  backend/tests/test_worker.py \
  backend/tests/test_api.py \
  -q
```

Expected: PASS

- [ ] **Step 2: Run the focused frontend test suite**

Run:

```bash
cd /root/WorkSpace/fotball-analyst/frontend
npm test -- --run \
  src/utils/uploadConfig.test.ts \
  src/components/StatsPanel.test.tsx \
  src/components/TeamSelectionBanner.test.tsx
npm run build
```

Expected: PASS

- [ ] **Step 3: Re-run the live 1-minute clip upload locally**

Use the actual frontend/backend dev servers with the trimmed clip and record:

- upload accepted
- job status transitions
- final job outcome
- if failure: exact error and log path
- if success: whether team selection remains unresolved honestly and tactical UI is paused appropriately

- [ ] **Step 4: Update the docs with the real outcome**

If the local upload path outcome changed materially, update:

- `README.md`
- `SESSION-HANDOFF.md`
- `REVIEW-FINDINGS.md` only for findings actually closed

---

## Success Definition For This Plan

This plan is complete when:

- unresolved team selection no longer silently assigns `my_team` / `enemy`
- player tracking remains visible before team selection
- untrusted-ball and unresolved-team runs block tactical interpretation
- auto-homography failure is operator-visible and actionable
- the upload-path API tests stop hanging
- the 1-minute local clip has been re-run and the result is documented truthfully
