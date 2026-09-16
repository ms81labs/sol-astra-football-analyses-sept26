import { useEffect, useRef, useState } from 'react';

import { shouldResyncVideo } from '../utils/videoSync';

interface MatchVideoPanelProps {
  videoUrl: string;
  currentTimestamp: number;
  isPlaying: boolean;
  onVideoTimeChange: (time: number) => void;
  onPlayingChange?: (playing: boolean) => void;
  seekVersion?: number;
  sourcePresentationFps?: number;
}

export default function MatchVideoPanel({
  videoUrl,
  currentTimestamp,
  isPlaying,
  onVideoTimeChange,
  onPlayingChange,
  seekVersion,
  sourcePresentationFps = 25,
}: MatchVideoPanelProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isReady, setIsReady] = useState(false);
  const appliedSeekRef = useRef<number | undefined>(undefined);
  const [hasError, setHasError] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);

  const stepSourceFrame = (direction: -1 | 1) => {
    const video = videoRef.current;
    if (!video || sourcePresentationFps <= 0) return;
    const step = 1 / sourcePresentationFps;
    const next = Math.max(0, (video.currentTime || 0) + direction * step);
    video.currentTime = next;
    onVideoTimeChange(next);
  };

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.playbackRate = playbackRate;
  }, [playbackRate]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !isReady || hasError) return;

    // Media ticks update the displayed frame; only explicit seeks move the video.
    if (seekVersion !== undefined && appliedSeekRef.current === seekVersion) return;
    appliedSeekRef.current = seekVersion;

    if (shouldResyncVideo(currentTimestamp, video.currentTime)) {
      video.currentTime = currentTimestamp;
    }
  }, [currentTimestamp, hasError, isReady, seekVersion]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !isReady || hasError) return;

    if (isPlaying) {
      try {
        const playPromise = video.play();
        if (playPromise && typeof playPromise.catch === 'function') {
          playPromise.catch(() => {
            onPlayingChange?.(false);
          });
        }
      } catch {
        onPlayingChange?.(false);
      }
      return;
    }

    if (!video.paused) {
      try {
        video.pause();
      } catch {
        onPlayingChange?.(false);
      }
    }
  }, [hasError, isPlaying, isReady, onPlayingChange]);

  return (
    <div className="relative h-full min-h-[260px] rounded-lg border border-slate-700 bg-slate-950 overflow-hidden">
      <video
        ref={videoRef}
        data-testid="match-video"
        src={videoUrl}
        controls
        playsInline
        preload="metadata"
        className="h-full w-full bg-slate-950 object-contain"
        onLoadedMetadata={() => setIsReady(true)}
        onPlay={() => onPlayingChange?.(true)}
        onPause={() => onPlayingChange?.(false)}
        onEnded={() => onPlayingChange?.(false)}
        onTimeUpdate={(event) => onVideoTimeChange(event.currentTarget.currentTime)}
        onError={() => {
          setIsReady(false);
          onPlayingChange?.(false);
          setHasError(true);
        }}
      />
      <div className="absolute bottom-2 left-2 flex items-center gap-2 rounded bg-slate-900/80 px-2 py-1 text-[11px] text-slate-300">
        <button
          type="button"
          onClick={() => stepSourceFrame(-1)}
          className="rounded border border-slate-600 px-1.5 py-0.5 hover:bg-slate-800"
        >
          Previous frame
        </button>
        <button
          type="button"
          onClick={() => stepSourceFrame(1)}
          className="rounded border border-slate-600 px-1.5 py-0.5 hover:bg-slate-800"
        >
          Next frame
        </button>
        <label>
          Playback speed
          <select
            value={playbackRate}
            onChange={(event) => setPlaybackRate(Number(event.target.value))}
            className="ml-2 rounded border border-slate-600 bg-slate-800 px-1 py-0.5 text-slate-200"
          >
            <option value={0.5}>0.5x</option>
            <option value={1}>1x</option>
            <option value={1.5}>1.5x</option>
            <option value={2}>2x</option>
          </select>
        </label>
      </div>

      {hasError && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-950/90 p-6 text-center">
          <div>
            <p className="text-sm font-semibold text-amber-300">Video unavailable</p>
            <p className="mt-2 text-xs text-slate-400">
              The original uploaded file could not be loaded for synced review.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
