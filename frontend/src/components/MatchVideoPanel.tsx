import { useEffect, useRef, useState } from 'react';

import { shouldResyncVideo } from '../utils/videoSync';
import { ApiError, readGeneration } from '../utils/request';

interface ReviewMaskOverlay {
  generationId: string;
  sourceFrameId: number;
  ptsSeconds: number;
  width: number;
  height: number;
  qualification: 'review_only';
  executionClass: 'stub' | 'real_model';
  masks: Array<{ objectId: string; trackId: string; rle: { size: [number, number]; counts: number[] } }>;
}

interface MatchVideoPanelProps {
  videoUrl: string;
  currentTimestamp: number;
  isPlaying: boolean;
  onVideoTimeChange: (time: number) => void;
  onPlayingChange?: (playing: boolean) => void;
  seekVersion?: number;
  sourcePresentationFps?: number;
  matchId?: string;
  generationId?: string | null;
  sourceFrameId?: number;
  sourceFramePts?: number;
}

export default function MatchVideoPanel({
  videoUrl,
  currentTimestamp,
  isPlaying,
  onVideoTimeChange,
  onPlayingChange,
  seekVersion,
  sourcePresentationFps = 25,
  matchId,
  generationId,
  sourceFrameId,
  sourceFramePts,
}: MatchVideoPanelProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [videoSize, setVideoSize] = useState<[number, number] | null>(null);
  const appliedSeekRef = useRef<number | undefined>(undefined);
  const [hasError, setHasError] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [showMasks, setShowMasks] = useState(false);
  const [maskResult, setMaskResult] = useState<{
    key: string; overlay: ReviewMaskOverlay | null; message: string;
  } | null>(null);
  const maskKey = `${matchId}:${generationId}:${sourceFrameId}:${sourceFramePts}`;
  const overlay = maskResult?.key === maskKey ? maskResult.overlay : null;
  const maskMessage = maskResult?.key === maskKey ? maskResult.message : '';
  const dimensionsMatch = overlay && isReady
    && videoSize?.[0] === overlay.width && videoSize?.[1] === overlay.height;

  useEffect(() => {
    if (!showMasks || isPlaying || !matchId || !generationId || sourceFrameId === undefined) return;
    const controller = new AbortController();
    let current = true;
    const path = `/api/matches/${encodeURIComponent(matchId)}/mask-overlay?frameId=${sourceFrameId}`;
    readGeneration<ReviewMaskOverlay>(path, generationId, controller.signal)
      .then((result) => {
        if (!current) return;
        if (result.sourceFrameId !== sourceFrameId || result.ptsSeconds !== sourceFramePts
            || result.qualification !== 'review_only') {
          setMaskResult({ key: maskKey, overlay: null, message: 'Review mask does not match this source frame.' });
          return;
        }
        setMaskResult({ key: maskKey, overlay: result,
          message: result.masks.length ? '' : 'No review mask for this frame.' });
      })
      .catch((error: unknown) => {
        if (!current) return;
        setMaskResult({ key: maskKey, overlay: null,
          message: error instanceof ApiError && error.status === 404
            ? 'No review mask for this frame.' : 'Review mask unavailable.' });
      });
    return () => { current = false; controller.abort(); };
  }, [showMasks, isPlaying, matchId, generationId, sourceFrameId, sourceFramePts, maskKey]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video || !overlay || !dimensionsMatch || isPlaying) return;
    const context = canvas.getContext('2d');
    if (!context) return;
    canvas.width = overlay.width;
    canvas.height = overlay.height;
    context.clearRect(0, 0, canvas.width, canvas.height);
    for (const item of overlay.masks) {
      const hue = [...item.trackId].reduce((value, char) => value + char.charCodeAt(0), 0) % 360;
      context.fillStyle = `hsla(${hue}, 90%, 55%, 0.35)`;
      let offset = 0;
      item.rle.counts.forEach((count, index) => {
        if (index % 2) {
          let remaining = count;
          while (remaining > 0) {
            const y = offset % overlay.height;
            const span = Math.min(remaining, overlay.height - y);
            context.fillRect(Math.floor(offset / overlay.height), y, 1, span);
            offset += span;
            remaining -= span;
          }
        } else {
          offset += count;
        }
      });
    }
  }, [overlay, dimensionsMatch, isPlaying]);

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
        onLoadedMetadata={(event) => {
          setVideoSize([event.currentTarget.videoWidth, event.currentTarget.videoHeight]);
          setIsReady(true);
        }}
        onPlay={() => { setMaskResult(null); onPlayingChange?.(true); }}
        onPause={() => onPlayingChange?.(false)}
        onEnded={() => onPlayingChange?.(false)}
        onTimeUpdate={(event) => onVideoTimeChange(event.currentTarget.currentTime)}
        onError={() => {
          setIsReady(false);
          setVideoSize(null);
          onPlayingChange?.(false);
          setHasError(true);
        }}
      />
      {showMasks && dimensionsMatch && !isPlaying && (
        <canvas ref={canvasRef} data-testid="review-mask-overlay" aria-label="Review mask overlay"
          className="pointer-events-none absolute inset-0 h-full w-full object-contain" />
      )}
      {showMasks && !isPlaying && (overlay?.masks.length || maskMessage) && (
        <div className="pointer-events-none absolute left-2 top-2 rounded bg-slate-950/85 px-2 py-1 text-[11px] text-white">
          {overlay?.masks.length && dimensionsMatch
            ? `Track ${overlay.masks.map((mask) => mask.trackId).join(', ')} · ${overlay.executionClass} · review only`
            : overlay && !dimensionsMatch ? 'Review mask dimensions do not match the video.' : maskMessage}
        </div>
      )}
      <div className="absolute bottom-2 left-2 flex items-center gap-2 rounded bg-slate-900/80 px-2 py-1 text-[11px] text-slate-300">
        <button
          type="button"
          onClick={() => stepSourceFrame(-1)}
          className="rounded border border-slate-600 px-1.5 py-0.5 hover:bg-slate-800"
        >
          Previous frame
        </button>
        {matchId && generationId && sourceFrameId !== undefined && (
          <button type="button" onClick={() => { setMaskResult(null); setShowMasks((value) => !value); }}
            aria-pressed={showMasks}
            className="rounded border border-slate-600 px-1.5 py-0.5 hover:bg-slate-800">
            {showMasks ? 'Hide review masks' : 'Show review masks'}
          </button>
        )}
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
