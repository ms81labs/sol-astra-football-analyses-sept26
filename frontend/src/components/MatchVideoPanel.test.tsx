import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import MatchVideoPanel from './MatchVideoPanel';

afterEach(() => {
  cleanup();
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
