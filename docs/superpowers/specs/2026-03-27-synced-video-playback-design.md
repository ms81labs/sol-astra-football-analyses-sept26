# Synced Video Playback Design

**Goal:** add synchronized browser playback for locally uploaded `video` matches so coaches can review the original footage alongside the tactical pitch and shared timeline.

**Status:** approved design, ready for implementation planning after user review.

## Why This Slice Next

The current workspace is strong on derived analytics, tactical overlays, and report generation, but review still happens only on the abstract pitch. For video-origin matches, the next highest-value improvement is letting the user inspect the original footage while keeping the existing tactical timeline as the shared review backbone.

This gives the product a much more coach-realistic workflow without widening into export, cloud media, or multi-camera concerns.

## Scope

### In Scope

- Browser playback for matches uploaded with `inputMode = "video"`
- Backend route for serving the original uploaded video file
- Frontend synchronized playback between the video element and tactical timeline
- Split review layout for video-backed matches
- Graceful fallback to pitch-only review if video loading fails

### Out Of Scope

- Playback for `tracking_json` matches
- Transcoding or re-encoding
- Streaming infrastructure beyond direct file serving
- Multi-camera playback
- Clip export
- Audio-specific features

## Recommended Approach

Serve the original uploaded video directly from the backend and synchronize a normal browser `<video>` element to the existing frame/timeline state.

This is the right tradeoff because:

- the backend already stores the uploaded source file path;
- the frontend already has a timeline and a canonical `currentFrame`;
- direct file playback is fast to implement and easy to reason about;
- it avoids unnecessary memory use compared with blob downloading.

## Architecture

### Current Shape

- The backend stores uploaded files and match metadata.
- The frontend renders a tactical pitch and a shared timeline.
- `currentFrame` is the canonical playback cursor in the app.
- Video-uploaded matches are processed, but the original footage is not surfaced in the UI.

### Proposed Shape

- Add a backend route: `GET /api/matches/{match_id}/video`
- For `video` matches, the frontend derives a direct video URL from the match id.
- Render a new `MatchVideoPanel` component only when the active match came from video input.
- Keep the tactical timeline and frame state as the synchronization source of truth.
- Let both pitch and video react to the same timeline/playback state.

## Backend Design

### New Route

Add:

- `GET /api/matches/{match_id}/video`

Behavior:

- look up the match by id
- verify the match exists
- verify `inputMode === "video"`
- resolve the original uploaded file path from storage
- return the file directly

### Error Cases

- `404` if the match does not exist
- `404` if the source file is missing
- `409` or `400` if the match is not a video-backed match

### Media Serving

Prefer FastAPI’s normal file-serving path so the browser can request the video directly and seek naturally. This should remain local-first and simple.

No transcoding should be introduced in this slice.

## Frontend Design

### Match Video Panel

Add a focused `MatchVideoPanel` component that:

- renders a `<video>` element for video-backed matches
- accepts `videoUrl`, `currentTimestamp`, `isPlaying`, and sync callbacks
- displays inline loading/failure UI

This component should be isolated so playback/sync behavior is testable without bloating `App.tsx`.

### Conditional Rendering

- If the active match was uploaded as `video`, render a split review area:
  - original video
  - tactical pitch
- If the active match was uploaded as `tracking_json`, keep the existing pitch-only layout

### Layout

For video matches:

- desktop: side-by-side video and tactical pitch
- smaller screens: stacked video above pitch

The existing timeline and overlay controls should remain below the review surface and continue to operate on the shared state.

## Synchronization Model

### Source Of Truth

`currentFrame` remains the source of truth for review state.

The video is synchronized to the timestamp of the current frame:

- `targetTime = matchData[currentFrame]?.Timestamp`

### Timeline To Video

When the user:

- presses play/pause
- scrubs the timeline
- steps through frames via existing controls

the video should be updated to match the same timestamp.

### Video To Timeline

When the user scrubs directly in the video:

- read the video `currentTime`
- map it to the nearest frame by timestamp
- update `currentFrame`

This keeps the pitch, analytics, and timeline in sync with the footage.

### Drift Handling

The sync should be tolerant, not hyper-reactive:

- only force-resync when drift exceeds a small threshold
- allow normal playback without constant seeks

The goal is smooth enough tactical review, not frame-perfect broadcast tooling.

## Utility Layer

Add small synchronization helpers on the frontend for:

- frame index -> timestamp
- video time -> nearest frame index
- drift check / resync decision

These should live outside the main component body so they are easy to test.

## UX States

### Loading

- show a small loading state in the video panel while metadata is loading

### Missing Or Failed Video

- show a compact inline warning in the video panel
- continue to render the pitch and timeline normally
- do not block the rest of the workspace

### Unsupported Match Type

- for non-video matches, do not show the video panel at all

## Testing Strategy

### Backend Tests

Add tests for:

- serving a video file for a video-backed match
- rejecting playback for non-video matches
- handling missing files safely

### Frontend Tests

Add tests for:

- nearest-frame timestamp mapping
- sync drift decisions
- conditional rendering of the video panel
- fallback rendering when the video fails to load

## Implementation Notes

- Keep the first version local-only and direct-file-based.
- Do not introduce media transcoding or background preprocessing for playback.
- Keep `App.tsx` as the orchestrator, but move actual video behavior into a focused component and small sync helpers.
- Preserve the existing timeline component as the main review control surface.

## Success Criteria

This slice is successful when:

- video-backed matches show the original footage in the app;
- timeline seek and play/pause keep video and pitch aligned;
- direct video scrubbing updates the tactical frame state;
- non-video matches continue to work unchanged;
- backend and frontend verification continue to pass.
