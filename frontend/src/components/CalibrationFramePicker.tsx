import { useMemo, useState } from 'react';

import type { PointInput } from '../utils/uploadConfig';
import { getNextCalibrationPointIndex, projectPreviewClickToSource } from '../utils/calibrationPoints';

const POINT_LABELS = ['Top Left', 'Top Right', 'Bottom Right', 'Bottom Left'] as const;

interface CalibrationFramePickerProps {
  previewUrl: string | null;
  pointInputs: PointInput[];
  onPointChange: (index: number, axis: 'x' | 'y', value: string) => void;
}

export default function CalibrationFramePicker({
  previewUrl,
  pointInputs,
  onPointChange,
}: CalibrationFramePickerProps) {
  const [videoDimensions, setVideoDimensions] = useState<{ width: number; height: number } | null>(null);
  const nextPointIndex = useMemo(() => getNextCalibrationPointIndex(pointInputs), [pointInputs]);

  if (!previewUrl) {
    return (
      <div className="rounded-lg border border-dashed border-slate-700 bg-slate-900/60 p-4 text-xs text-slate-400">
        Load a video to unlock click-to-fill calibration on the first frame.
      </div>
    );
  }

  const nextLabel = nextPointIndex === null ? null : POINT_LABELS[nextPointIndex];

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-xs text-slate-300">
          {nextLabel
            ? `Click next: ${nextLabel}, or enter ${nextLabel} X and ${nextLabel} Y above.`
            : 'All four points are set. Reset points to pick them again.'}
        </p>
        <p className="text-[11px] text-slate-500">Preview uses the first frame of the selected video.</p>
      </div>
      <div className="relative overflow-hidden rounded-lg border border-slate-700 bg-slate-950">
        <video
          data-testid="calibration-preview"
          src={previewUrl}
          muted
          playsInline
          preload="metadata"
          className="max-h-[360px] w-full object-contain"
          onLoadedMetadata={(event) => {
            const video = event.currentTarget;
            video.currentTime = 0;
            setVideoDimensions({ width: video.videoWidth, height: video.videoHeight });
          }}
          onClick={(event) => {
            if (nextPointIndex === null || !videoDimensions) {
              return;
            }
            const rect = event.currentTarget.getBoundingClientRect();
            const projected = projectPreviewClickToSource({
              clickX: event.clientX,
              clickY: event.clientY,
              rectLeft: rect.left,
              rectTop: rect.top,
              rectWidth: rect.width,
              rectHeight: rect.height,
              sourceWidth: videoDimensions.width,
              sourceHeight: videoDimensions.height,
            });
            onPointChange(nextPointIndex, 'x', String(projected.x));
            onPointChange(nextPointIndex, 'y', String(projected.y));
          }}
        />
      </div>
    </div>
  );
}
