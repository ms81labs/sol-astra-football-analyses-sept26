# Synced Video Playback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** let locally uploaded `video` matches play their original footage in the browser while staying synchronized with the existing tactical pitch and shared timeline.

**Architecture:** add a backend media route that serves the original uploaded file for `video` matches, keep `currentFrame` as the canonical review state in the frontend, and introduce a focused `MatchVideoPanel` plus small sync helpers that translate between video time and frame timestamps. The slice is additive: `tracking_json` matches stay pitch-only and existing analysis/report flows remain unchanged.

**Tech Stack:** FastAPI, Python, React 19, TypeScript, Vitest, Testing Library.

---

## File Structure

- Modify: `/root/WorkSpace/fotball-analyst/backend/app/main.py`
  Purpose: add the backend video-serving route
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_api.py`
  Purpose: regression coverage for the video route
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.ts`
  Purpose: expose a canonical video URL helper
- Create: `/root/WorkSpace/fotball-analyst/frontend/src/utils/videoSync.ts`
  Purpose: timestamp/frame sync helpers used by the video panel and app
- Create: `/root/WorkSpace/fotball-analyst/frontend/src/utils/videoSync.test.ts`
  Purpose: regression coverage for nearest-frame and drift logic
- Create: `/root/WorkSpace/fotball-analyst/frontend/src/components/MatchVideoPanel.tsx`
  Purpose: focused browser video playback with sync callbacks and fallback states
- Create: `/root/WorkSpace/fotball-analyst/frontend/src/components/MatchVideoPanel.test.tsx`
  Purpose: component coverage for conditional states and callback behavior
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/App.tsx`
  Purpose: render video/pitch split view for video matches and wire shared playback state

## Task 1: Add Failing Backend Tests For The Video Route

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/backend/tests/test_api.py`

- [ ] **Step 1: Write the failing success-path test**

Add a test that uploads a `video` match with inline job processing and then requests the new media route:

```python
def test_video_route_serves_uploaded_file_for_video_matches(tmp_path: Path, monkeypatch):
    storage_root = tmp_path / "storage"
    app = create_app(storage_root=storage_root, run_jobs_inline=True)
    client = TestClient(app)

    def fake_video_processor(video_path, config):  # noqa: ANN001
        return {
            "rows": [
                {"Frame_ID": 0, "Timestamp": 0.0, "Entity_Type": "ball", "Track_ID": 0, "X": 50.0, "Y": 50.0, "Conf": 0.9},
            ],
            "trackColors": {},
        }

    monkeypatch.setattr("backend.app.processor.process_video_input", fake_video_processor, raising=False)

    response = client.post(
        "/api/matches",
        data={
            "name": "Video Match",
            "inputMode": "video",
            "config": json.dumps(
                {
                    "manualHomographyPoints": [
                        {"x": 0.0, "y": 0.0},
                        {"x": 100.0, "y": 0.0},
                        {"x": 100.0, "y": 100.0},
                        {"x": 0.0, "y": 100.0},
                    ],
                }
            ),
        },
        files={"file": ("sample.mp4", b"video-binary", "video/mp4")},
    )

    match_id = response.json()["matchId"]
    video_response = client.get(f"/api/matches/{match_id}/video")

    assert video_response.status_code == 200
    assert video_response.content == b"video-binary"
    assert video_response.headers["content-type"].startswith("video/mp4")
```

- [ ] **Step 2: Write the failing non-video rejection test**

```python
def test_video_route_rejects_tracking_json_matches(tmp_path: Path):
    ...
    video_response = client.get(f"/api/matches/{match_id}/video")
    assert video_response.status_code == 409
```

- [ ] **Step 3: Run the targeted backend tests to verify RED**

Run:
```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_api.py -q
```

Expected: FAIL because the `/api/matches/{match_id}/video` route does not exist yet.

## Task 2: Add Failing Frontend Tests For Sync Helpers

**Files:**
- Create: `/root/WorkSpace/fotball-analyst/frontend/src/utils/videoSync.test.ts`

- [ ] **Step 1: Write a nearest-frame mapping test**

```ts
import { describe, expect, it } from 'vitest';
import { findNearestFrameIndex, shouldResyncVideo } from './videoSync';

describe('findNearestFrameIndex', () => {
  it('maps video time to the nearest frame timestamp', () => {
    expect(findNearestFrameIndex([0, 0.2, 0.4, 0.8], 0.37)).toBe(2);
    expect(findNearestFrameIndex([0, 0.2, 0.4, 0.8], 0.79)).toBe(3);
  });
});

describe('shouldResyncVideo', () => {
  it('only forces sync when drift exceeds the threshold', () => {
    expect(shouldResyncVideo(1.0, 1.04, 0.08)).toBe(false);
    expect(shouldResyncVideo(1.0, 1.15, 0.08)).toBe(true);
  });
});
```

- [ ] **Step 2: Run the utility test to verify RED**

Run:
```bash
npm test -- src/utils/videoSync.test.ts
```

Expected: FAIL because the sync helper file does not exist yet.

## Task 3: Add Failing Frontend Component Tests For Video Playback

**Files:**
- Create: `/root/WorkSpace/fotball-analyst/frontend/src/components/MatchVideoPanel.test.tsx`

- [ ] **Step 1: Write the failing video panel render test**

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import MatchVideoPanel from './MatchVideoPanel';

describe('MatchVideoPanel', () => {
  it('renders a video element and reports direct scrubbing back to the app', () => {
    const onVideoTimeChange = vi.fn();

    render(
      <MatchVideoPanel
        videoUrl="/api/matches/match-1/video"
        currentTimestamp={1.2}
        isPlaying={false}
        onVideoTimeChange={onVideoTimeChange}
      />,
    );

    const video = screen.getByTestId('match-video') as HTMLVideoElement;
    Object.defineProperty(video, 'currentTime', { configurable: true, value: 2.4, writable: true });

    fireEvent.loadedMetadata(video);
    fireEvent.timeUpdate(video);

    expect(onVideoTimeChange).toHaveBeenCalledWith(2.4);
  });

  it('shows an inline fallback when the video errors', () => {
    render(
      <MatchVideoPanel
        videoUrl="/api/matches/match-1/video"
        currentTimestamp={0}
        isPlaying={false}
        onVideoTimeChange={() => {}}
      />,
    );

    fireEvent.error(screen.getByTestId('match-video'));

    expect(screen.getByText(/video unavailable/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run the component test to verify RED**

Run:
```bash
npm test -- src/components/MatchVideoPanel.test.tsx
```

Expected: FAIL because the component does not exist yet.

## Task 4: Implement Backend Video Serving

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/backend/app/main.py`

- [ ] **Step 1: Add the required import**

Add:

```python
from fastapi.responses import FileResponse
```

- [ ] **Step 2: Add the `/api/matches/{match_id}/video` route**

Implement:

```python
    @app.get("/api/matches/{match_id}/video")
    def get_match_video(match_id: str):
        try:
            match = storage.get_match(match_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Match not found") from exc

        if match.inputMode != "video":
            raise HTTPException(status_code=409, detail="Video playback is only available for video-backed matches.")

        video_path = storage.get_match_input_path(match_id)
        if not video_path.exists():
            raise HTTPException(status_code=404, detail="Video file not found.")

        return FileResponse(video_path, media_type="video/mp4", filename=match.originalFilename)
```

- [ ] **Step 3: Run backend tests to verify GREEN**

Run:
```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests/test_api.py -q
```

Expected: PASS

## Task 5: Implement Frontend Sync Helpers

**Files:**
- Create: `/root/WorkSpace/fotball-analyst/frontend/src/utils/videoSync.ts`

- [ ] **Step 1: Add the small helper module**

Implement:

```ts
export function buildFrameTimestamps(timestamps: number[]): number[] {
  return timestamps;
}

export function findNearestFrameIndex(frameTimestamps: number[], videoTime: number): number {
  if (frameTimestamps.length === 0) return 0;
  let bestIndex = 0;
  let bestDistance = Math.abs(frameTimestamps[0] - videoTime);
  for (let index = 1; index < frameTimestamps.length; index += 1) {
    const distance = Math.abs(frameTimestamps[index] - videoTime);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  }
  return bestIndex;
}

export function shouldResyncVideo(targetTime: number, currentTime: number, threshold = 0.08): boolean {
  return Math.abs(targetTime - currentTime) > threshold;
}
```

- [ ] **Step 2: Run the utility tests to verify GREEN**

Run:
```bash
npm test -- src/utils/videoSync.test.ts
```

Expected: PASS

## Task 6: Implement MatchVideoPanel

**Files:**
- Create: `/root/WorkSpace/fotball-analyst/frontend/src/components/MatchVideoPanel.tsx`

- [ ] **Step 1: Build the focused video component**

Implement a component that:

- renders a `<video data-testid="match-video">`
- accepts `videoUrl`, `currentTimestamp`, `isPlaying`, `onVideoTimeChange`
- uses `useEffect` plus a `ref` to sync the element to app state
- calls `play()` / `pause()` when `isPlaying` changes
- calls `onVideoTimeChange(video.currentTime)` on `timeupdate`
- shows a loading label before metadata arrives
- shows `Video unavailable.` after an error

- [ ] **Step 2: Run the component test to verify GREEN**

Run:
```bash
npm test -- src/components/MatchVideoPanel.test.tsx
```

Expected: PASS

## Task 7: Wire Synced Video Into App

**Files:**
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/utils/api.ts`
- Modify: `/root/WorkSpace/fotball-analyst/frontend/src/App.tsx`

- [ ] **Step 1: Add a small API helper**

In `frontend/src/utils/api.ts`, add:

```ts
export function buildMatchVideoUrl(matchId: string): string {
  return `/api/matches/${matchId}/video`;
}
```

- [ ] **Step 2: Import the video helpers and component into `App.tsx`**

Add imports for:

- `MatchVideoPanel`
- `buildMatchVideoUrl`
- `findNearestFrameIndex`
- `shouldResyncVideo`

- [ ] **Step 3: Compute video-match state**

Add memos like:

```ts
const isVideoMatch = activeMatch?.detail.inputMode === 'video';
const frameTimestamps = useMemo(() => matchData.map((frame) => frame.Timestamp), [matchData]);
const currentTimestamp = matchData[currentFrame]?.Timestamp ?? 0;
```

- [ ] **Step 4: Add a handler for direct video scrubbing**

```ts
const handleVideoTimeChange = useCallback((time: number) => {
  const nextFrame = findNearestFrameIndex(frameTimestamps, time);
  setCurrentFrame(nextFrame);
}, [frameTimestamps]);
```

- [ ] **Step 5: Render the split review surface for video matches**

Replace the single pitch-only render branch with:

- side-by-side `MatchVideoPanel` + `TacticalPitch` for video matches
- existing `TacticalPitch` only for non-video matches

Keep the loading/error/empty states as they are today.

- [ ] **Step 6: Keep timeline as the shared playback source**

Pass:

- `videoUrl={buildMatchVideoUrl(activeMatch.id)}`
- `currentTimestamp={currentTimestamp}`
- `isPlaying={isPlaying}`
- `onVideoTimeChange={handleVideoTimeChange}`

and let the existing timeline/playback controls continue driving `currentFrame`.

- [ ] **Step 7: Run the focused frontend tests**

Run:
```bash
npm test -- src/components/MatchVideoPanel.test.tsx
npm test -- src/utils/videoSync.test.ts
```

Expected: PASS

## Task 8: Full Verification

**Files:**
- Verify only

- [ ] **Step 1: Run backend tests**

```bash
PYTHONPATH=/root/WorkSpace/fotball-analyst /tmp/fotball-analyst-testenv/bin/pytest /root/WorkSpace/fotball-analyst/backend/tests -q
```

Expected: PASS

- [ ] **Step 2: Run frontend tests**

```bash
npm test
```

Expected: PASS

- [ ] **Step 3: Run the frontend build**

```bash
npm run build
```

Expected: PASS

- [ ] **Step 4: Run frontend lint**

```bash
npm run lint
```

Expected: PASS

- [ ] **Step 5: Run backend syntax verification**

```bash
python3 -m py_compile /root/WorkSpace/fotball-analyst/backend/app/*.py /root/WorkSpace/fotball-analyst/backend/run_guerilla.py /root/WorkSpace/fotball-analyst/backend/train_custom.py
```

Expected: PASS

- [ ] **Step 6: Summarize roadmap progress**

Call out:

- video-backed matches now support synced local playback
- pitch and footage share the same timeline cursor
- the next strongest slice is report export if we want coach-ready output, or annotation/review tools if we want deeper workflow next
