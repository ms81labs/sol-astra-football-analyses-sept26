import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import MatchVideoPanel from './MatchVideoPanel';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

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
    fireEvent.loadedMetadata(video);
    video.currentTime = 2.4;
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


it('steps one source presentation frame and does not treat target fps as the step', () => {
  render(
    <MatchVideoPanel
      videoUrl="/api/matches/match-1/video"
      currentTimestamp={0}
      isPlaying={false}
      onVideoTimeChange={() => undefined}
      sourcePresentationFps={25}
    />,
  );
  const video = screen.getByTestId('match-video') as HTMLVideoElement;
  fireEvent.loadedMetadata(video);
  fireEvent.click(screen.getByRole('button', { name: /next frame/i }));
  expect(video.currentTime).toBeCloseTo(0.04);
  fireEvent.click(screen.getByRole('button', { name: /previous frame/i }));
  expect(video.currentTime).toBeCloseTo(0);
  expect(screen.queryByText(/inference/i)).toBeNull();
});

it('exposes variable playback speed without treating it as inference fps', () => {
  render(
    <MatchVideoPanel
      videoUrl="/api/matches/match-1/video"
      currentTimestamp={0}
      isPlaying={false}
      onVideoTimeChange={() => undefined}
    />,
  );
  const video = screen.getByTestId('match-video') as HTMLVideoElement;
  fireEvent.change(screen.getByLabelText(/playback speed/i), { target: { value: '0.5' } });
  expect(video.playbackRate).toBe(0.5);
});


it('seeks during playback, ignores frame ticks, and reapplies pre-metadata play intent', () => {
  const play = vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue();
  const onVideoTimeChange = vi.fn();
  const props = { videoUrl: '/video', currentTimestamp: 0, isPlaying: true, onVideoTimeChange, seekVersion: 0 };
  const { rerender } = render(<MatchVideoPanel {...props} />);
  const video = screen.getByTestId('match-video') as HTMLVideoElement;
  fireEvent.loadedMetadata(video);
  expect(play).toHaveBeenCalledOnce();
  video.currentTime = 1.31;
  fireEvent.timeUpdate(video);
  rerender(<MatchVideoPanel {...props} currentTimestamp={1.2} />);
  expect(video.currentTime).toBe(1.31);
  rerender(<MatchVideoPanel {...props} currentTimestamp={8} seekVersion={1} />);
  expect(video.currentTime).toBe(8);
  play.mockRestore();
});

it('reports native playback state including ended and rejected play', async () => {
  const onPlayingChange = vi.fn();
  const play = vi.spyOn(HTMLMediaElement.prototype, 'play').mockRejectedValue(new Error('blocked'));
  render(<MatchVideoPanel videoUrl="/video" currentTimestamp={0} isPlaying onVideoTimeChange={() => {}} onPlayingChange={onPlayingChange} />);
  const video = screen.getByTestId('match-video');
  fireEvent.play(video);
  expect(onPlayingChange).toHaveBeenLastCalledWith(true);
  fireEvent.pause(video);
  expect(onPlayingChange).toHaveBeenLastCalledWith(false);
  fireEvent.ended(video);
  expect(onPlayingChange).toHaveBeenLastCalledWith(false);
  onPlayingChange.mockClear();
  fireEvent.loadedMetadata(video);
  await Promise.resolve();
  expect(onPlayingChange).toHaveBeenLastCalledWith(false);
  play.mockRestore();
});

it('shows a source-frame review mask over the original video with its track mapping', async () => {
  const fillRect = vi.fn();
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ clearRect: vi.fn(), fillRect } as unknown as CanvasRenderingContext2D);
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({
    generationId: 'gen_one', sourceFrameId: 4, ptsSeconds: 0.16, width: 2, height: 2,
    qualification: 'review_only', executionClass: 'stub',
    masks: [{ objectId: 'o1', trackId: '7', rle: { size: [2, 2], counts: [0, 2, 2] } }],
  }) });
  vi.stubGlobal('fetch', fetch);
  render(<MatchVideoPanel videoUrl="/video" currentTimestamp={0.16} isPlaying={false}
    onVideoTimeChange={() => {}} matchId="m1" generationId="gen_one" sourceFrameId={4} sourceFramePts={0.16} />);
  const video = screen.getByTestId('match-video') as HTMLVideoElement;
  Object.defineProperties(video, { videoWidth: { value: 2 }, videoHeight: { value: 2 } });
  fireEvent.loadedMetadata(video);
  fireEvent.click(screen.getByRole('button', { name: /show review masks/i }));
  await waitFor(() => expect(fillRect).toHaveBeenCalledWith(0, 0, 1, 2));
  expect(fetch).toHaveBeenCalledWith('/api/matches/m1/mask-overlay?frameId=4&generationId=gen_one', expect.anything());
  expect(screen.getByText(/track 7.*stub.*review only/i)).toBeTruthy();
  expect(video.src).toContain('/video');
});

it('ignores an old mask response after the generation changes', async () => {
  let resolveOld!: (value: unknown) => void;
  const fetch = vi.fn().mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }))
    .mockResolvedValue({ ok: false, status: 404, json: async () => ({}) });
  vi.stubGlobal('fetch', fetch);
  const props = { videoUrl: '/video', currentTimestamp: 0.16, isPlaying: false,
    onVideoTimeChange: () => {}, matchId: 'm1', sourceFrameId: 4, sourceFramePts: 0.16 };
  const { rerender } = render(<MatchVideoPanel {...props} generationId="gen_one" />);
  fireEvent.loadedMetadata(screen.getByTestId('match-video'));
  fireEvent.click(screen.getByRole('button', { name: /show review masks/i }));
  rerender(<MatchVideoPanel {...props} generationId="gen_two" />);
  resolveOld({ ok: true, json: async () => ({ generationId: 'gen_one', sourceFrameId: 4,
    ptsSeconds: 0.16, width: 2, height: 2, qualification: 'review_only', executionClass: 'stub', masks: [] }) });
  await waitFor(() => expect(screen.getByText(/no review mask for this frame/i)).toBeTruthy());
  expect(screen.queryByText(/track 7/i)).toBeNull();
});
