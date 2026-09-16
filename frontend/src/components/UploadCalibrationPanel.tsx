import type { PointInput } from '../utils/uploadConfig';
import type { CameraProfile, UploadConfig } from '../types';
import CalibrationFramePicker from './CalibrationFramePicker';

interface UploadCalibrationPanelProps {
  autoHomography: boolean;
  loadedVideoConfig?: UploadConfig | null;
  attackDirection: 'left_to_right' | 'right_to_left';
  cameraProfile?: CameraProfile;
  pointInputs: PointInput[];
  previewUrl: string | null;
  canRetryUpload: boolean;
  isRetryingUpload: boolean;
  uploadFailureGuidance: string | null;
  onAutoHomographyChange: (value: boolean) => void;
  onAttackDirectionChange: (value: 'left_to_right' | 'right_to_left') => void;
  onCameraProfileChange?: (value: CameraProfile) => void;
  onPointChange: (index: number, axis: 'x' | 'y', value: string) => void;
  onResetPoints: () => void;
  onRetryUpload: () => void;
  pitchLengthM?: string;
  pitchWidthM?: string;
  periodOneEnd?: string;
  cloudPermission?: boolean;
  retentionClass?: 'working' | 'review' | 'publication' | 'unknown';
  onPitchLengthChange?: (value: string) => void;
  onPitchWidthChange?: (value: string) => void;
  onPeriodOneEndChange?: (value: string) => void;
  onCloudPermissionChange?: (value: boolean) => void;
  onRetentionClassChange?: (value: 'working' | 'review' | 'publication' | 'unknown') => void;
}

const POINT_LABELS = ['Top Left', 'Top Right', 'Bottom Right', 'Bottom Left'] as const;
const KEYBOARD_INSTRUCTIONS_ID = 'manual-calibration-keyboard-instructions';

export default function UploadCalibrationPanel({
  autoHomography,
  loadedVideoConfig,
  attackDirection,
  cameraProfile = 'stitched_panoramic_view',
  pointInputs,
  previewUrl,
  canRetryUpload,
  isRetryingUpload,
  uploadFailureGuidance,
  onAutoHomographyChange,
  onAttackDirectionChange,
  onCameraProfileChange,
  onPointChange,
  onResetPoints,
  onRetryUpload,
  pitchLengthM = '',
  pitchWidthM = '',
  periodOneEnd = '',
  cloudPermission = false,
  retentionClass = 'unknown',
  onPitchLengthChange,
  onPitchWidthChange,
  onPeriodOneEndChange,
  onCloudPermissionChange,
  onRetentionClassChange,
}: UploadCalibrationPanelProps) {
  const showManualRecovery = Boolean(uploadFailureGuidance) && autoHomography;
  const loadedCalibrationMode = loadedVideoConfig === undefined ? null
    : loadedVideoConfig?.autoHomography ? 'automatic detection requested'
      : loadedVideoConfig?.manualHomographyPoints?.length === 4 ? 'manual corners supplied'
        : 'calibration mode unavailable';

  return (
    <section className="mb-6 bg-slate-800 rounded-xl border border-slate-700 p-4">
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">Next Upload Calibration</h2>
            <p className="text-xs text-slate-400">These settings affect only the next upload or retry. Tracking JSON ignores them; a loaded match keeps its saved configuration.</p>
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={autoHomography}
              onChange={(event) => onAutoHomographyChange(event.target.checked)}
              className="w-4 h-4 accent-emerald-500"
            />
            Auto-detect pitch
          </label>
          <label className="text-xs text-slate-400 flex items-center gap-2">
            Camera profile
            <select
              aria-label="Camera profile"
              value={cameraProfile}
              onChange={(event) => onCameraProfileChange?.(event.target.value as CameraProfile)}
              className="bg-slate-900 text-slate-200 text-xs px-3 py-2 rounded border border-slate-700 font-mono"
            >
              <option value="stitched_panoramic_view">Stitched panoramic</option>
              <option value="stable_elevated_wide">Stable elevated wide</option>
              <option value="broadcast_cuts_zoom">Broadcast with cuts</option>
              <option value="handheld_low_angle">Handheld / low angle</option>
            </select>
          </label>
          <label className="text-xs text-slate-400 flex items-center gap-2">
            Attack direction
            <select
              value={attackDirection}
              onChange={(event) => onAttackDirectionChange(event.target.value as 'left_to_right' | 'right_to_left')}
              className="bg-slate-900 text-slate-200 text-xs px-3 py-2 rounded border border-slate-700 font-mono"
            >
              <option value="left_to_right">Left to right</option>
              <option value="right_to_left">Right to left</option>
            </select>
          </label>
        </div>

        {loadedCalibrationMode && (
          <p className="text-xs text-amber-200/90">
            Loaded video: {loadedCalibrationMode}. This setting does not verify pitch-coordinate accuracy.
          </p>
        )}

        {showManualRecovery && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="space-y-1">
                <p className="text-sm font-semibold text-amber-200">Auto-detect missed the pitch</p>
                <p className="text-xs text-amber-100/90">{uploadFailureGuidance}</p>
                <p className="text-xs text-amber-200/80">Corner order: Top Left, Top Right, Bottom Right, Bottom Left.</p>
              </div>
              <button
                type="button"
                onClick={() => onAutoHomographyChange(false)}
                className="rounded border border-amber-400/40 bg-amber-500/15 px-3 py-1.5 text-xs font-semibold text-amber-100 hover:bg-amber-500/25 transition-colors"
              >
                Switch to manual calibration
              </button>
            </div>
          </div>
        )}

        {!autoHomography && (
          <>
            <div className="flex items-center justify-between gap-3 flex-wrap rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2">
              <p className="text-xs text-slate-300">Use the visible pitch corners in order: Top Left, Top Right, Bottom Right, Bottom Left.</p>
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={onRetryUpload}
                  disabled={!canRetryUpload || isRetryingUpload}
                  className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-100 transition-colors enabled:hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
                >
                  {isRetryingUpload ? 'Retrying upload...' : 'Retry last video with current calibration'}
                </button>
                <button
                  type="button"
                  onClick={onResetPoints}
                  className="rounded border border-slate-600 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-700 transition-colors"
                >
                  Reset points
                </button>
              </div>
            </div>
            <p id={KEYBOARD_INSTRUCTIONS_ID} className="text-xs text-slate-400">
              Keyboard: enter source-frame X and Y pixel coordinates in the named fields below. The preview is an optional click-to-fill shortcut.
            </p>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {POINT_LABELS.map((label, index) => (
                <div key={label} className="bg-slate-900 rounded-lg border border-slate-700 p-3">
                  <p className="text-xs text-slate-400 mb-2">{label}</p>
                  <div className="flex gap-2">
                    {(['x', 'y'] as const).map((axis) => (
                      <label key={axis} className="w-full text-xs text-slate-400">
                        <span className="sr-only">{`${label} ${axis.toUpperCase()}`}</span>
                        <span aria-hidden="true" className="uppercase">{axis}</span>
                        <input
                          type="number"
                          inputMode="numeric"
                          value={pointInputs[index]?.[axis] ?? ''}
                          onChange={(event) => onPointChange(index, axis, event.target.value)}
                          aria-describedby={KEYBOARD_INSTRUCTIONS_ID}
                          className="mt-1 w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-xs text-slate-200"
                        />
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <CalibrationFramePicker
              previewUrl={previewUrl}
              pointInputs={pointInputs}
              onPointChange={onPointChange}
            />
          </>
        )}

        {autoHomography && !showManualRecovery && (
          <p className="text-xs text-emerald-400/70 italic">
            Next video upload will try automatic pitch detection. If it misses, switch to manual corners and retry.
          </p>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 rounded-lg border border-slate-700 bg-slate-900/70 p-3">
          <label className="text-xs text-slate-400">
            Pitch length (m)
            <input
              aria-label="Pitch length (m)"
              type="number"
              value={pitchLengthM}
              onChange={(event) => onPitchLengthChange?.(event.target.value)}
              className="mt-1 w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-xs text-slate-200"
            />
          </label>
          <label className="text-xs text-slate-400">
            Pitch width (m)
            <input
              aria-label="Pitch width (m)"
              type="number"
              value={pitchWidthM}
              onChange={(event) => onPitchWidthChange?.(event.target.value)}
              className="mt-1 w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-xs text-slate-200"
            />
          </label>
          <label className="text-xs text-slate-400">
            First-half end (s)
            <input
              aria-label="First-half end (s)"
              type="number"
              value={periodOneEnd}
              onChange={(event) => onPeriodOneEndChange?.(event.target.value)}
              className="mt-1 w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-xs text-slate-200"
            />
          </label>
          <label className="text-xs text-slate-400">
            Retention class
            <input
              aria-label="Retention class"
              value={retentionClass}
              onChange={(event) => onRetentionClassChange?.(event.target.value as 'working' | 'review' | 'publication' | 'unknown')}
              className="mt-1 w-full bg-slate-950 border border-slate-700 rounded px-2 py-1.5 text-xs text-slate-200"
            />
          </label>
          <label className="flex items-center gap-2 text-xs text-slate-300 md:col-span-2">
            <input
              aria-label="Allow cloud processing"
              type="checkbox"
              checked={cloudPermission}
              onChange={(event) => onCloudPermissionChange?.(event.target.checked)}
              className="w-4 h-4 accent-emerald-500"
            />
            Allow cloud processing
          </label>
        </div>
      </div>
    </section>
  );
}
