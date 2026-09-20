import { useState } from 'react';

interface TeamCluster {
  id: number | string;
  label: string;
}

interface LandmarkPreview {
  residualP95M: number | null;
  accepted: boolean;
  committed: boolean;
  measured?: boolean;
}

export interface SetupWizardSavePayload {
  cameraProfile: string;
  pitchLengthM: number | null;
  periods: Array<{ name: string; startSeconds: number; endSeconds: number }>;
  rights: { cloudPermission: boolean; processingScope: 'local_only' | 'hosted' };
  homeTeam: string;
  awayTeam: string;
}

interface SetupWizardProps {
  cameraProfile: string;
  pitchLengthM?: string;
  automationAdmitted?: boolean;
  manualTaggingPermitted?: boolean;
  cannotMeasure?: string[];
  teamClusters?: TeamCluster[];
  landmarkPreview?: LandmarkPreview | null;
  matchId?: string;
  homeTeam?: string;
  awayTeam?: string;
  cloudPermission?: boolean;
  periods?: string;
  onSave?: (payload: SetupWizardSavePayload) => Promise<void> | void;
  onSaveMetadata?: (payload: Pick<SetupWizardSavePayload, 'homeTeam' | 'awayTeam'>) => Promise<void>;
  onSavePolicy?: (payload: SetupWizardSavePayload['rights']) => Promise<void>;
  separateLiveSettings?: boolean;
  periodDefinitions?: SetupWizardSavePayload['periods'];
  onCommitCalibration?: (payload: { committed: boolean; certified: boolean }) => void;
}

const CAMERA_PROFILES = [
  'stable_elevated_wide',
  'stitched_panoramic_view',
  'broadcast_cuts_zoom',
  'handheld_low_angle',
] as const;

export default function SetupWizard({
  cameraProfile,
  pitchLengthM = '',
  automationAdmitted = false,
  manualTaggingPermitted = true,
  cannotMeasure = [],
  teamClusters = [],
  landmarkPreview = null,
  matchId,
  homeTeam = '',
  awayTeam = '',
  cloudPermission = false,
  periods = '1,2',
  onSave,
  onCommitCalibration,
  onSaveMetadata, onSavePolicy, separateLiveSettings = false, periodDefinitions,
}: SetupWizardProps) {
  const [periodText, setPeriodText] = useState(periods);
  const [pitch, setPitch] = useState(pitchLengthM);
  const [camera, setCamera] = useState(cameraProfile);
  const [home, setHome] = useState(homeTeam);
  const [away, setAway] = useState(awayTeam);
  const [cloud, setCloud] = useState(cloudPermission);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [liveSaving, setLiveSaving] = useState(false);
  const [liveMessage, setLiveMessage] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<'idle' | 'pending' | 'saved' | 'conflicted'>('idle');

  async function handleSave() {
    if (!onSave) return;
    setSaveState('pending');
    setSaveMessage(null);
    const names = periodText.split(',').map((item) => item.trim()).filter(Boolean);
    const payload: SetupWizardSavePayload = {
      cameraProfile: camera,
      pitchLengthM: pitch.trim() === '' ? null : Number(pitch),
      periods: names.map((name, index) => ({
        name,
        startSeconds: periodDefinitions?.[index]?.startSeconds ?? index * 45 * 60,
        endSeconds: periodDefinitions?.[index]?.endSeconds ?? (index + 1) * 45 * 60,
      })),
      rights: {
        cloudPermission: cloud,
        processingScope: cloud ? 'hosted' : 'local_only',
      },
      homeTeam: home,
      awayTeam: away,
    };
    try {
      await onSave(payload);
      setSaveState('saved');
    } catch (error) {
      setSaveState('conflicted');
      setSaveMessage(error instanceof Error ? error.message : 'Setup application was not confirmed.');
    }
  }

  async function saveLive(action: 'metadata' | 'policy') {
    if (liveSaving) return;
    setLiveSaving(true);
    setLiveMessage(null);
    try {
      if (action === 'metadata') await onSaveMetadata?.({ homeTeam: home, awayTeam: away });
      else await onSavePolicy?.({ cloudPermission: cloud, processingScope: cloud ? 'hosted' : 'local_only' });
      setLiveMessage(action === 'metadata' ? 'Team names saved separately.' : 'Current cloud permission saved separately.');
    } catch (error) { setLiveMessage(error instanceof Error ? error.message : 'Live settings not saved.'); }
    finally { setLiveSaving(false); }
  }

  return (
    <section aria-label="Setup wizard" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Setup wizard</h4>
      {matchId && <p className="text-xs text-slate-500">Match {matchId}</p>}
      <label className="block text-xs text-slate-400">
        Periods
        <input
          value={periodText}
          onChange={(event) => setPeriodText(event.target.value)}
          className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200"
        />
      </label>
      <label className="block text-xs text-slate-400">
        Pitch length (m)
        <input
          value={pitch}
          onChange={(event) => setPitch(event.target.value)}
          className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200"
        />
      </label>
      <label className="block text-xs text-slate-400">
        Camera profile
        <select
          value={camera}
          onChange={(event) => setCamera(event.target.value)}
          className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200"
        >
          {CAMERA_PROFILES.map((profile) => (
            <option key={profile} value={profile}>{profile}</option>
          ))}
        </select>
      </label>
      <label className="block text-xs text-slate-400">
        Home team
        <input
          value={home}
          onChange={(event) => setHome(event.target.value)}
          className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200"
        />
      </label>
      <label className="block text-xs text-slate-400">
        Away team
        <input
          value={away}
          onChange={(event) => setAway(event.target.value)}
          className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200"
        />
      </label>
      {onSaveMetadata && <button type="button" disabled={liveSaving} onClick={() => void saveLive('metadata')}
        className="rounded border border-slate-600 px-3 py-1 text-xs">Save team names</button>}
      <p className="text-xs text-slate-400">Team mapping: colour clusters are suggestions, not semantic home/away labels.</p>
      {teamClusters.map((cluster) => (
        <p key={cluster.id} className="text-xs text-slate-300">{cluster.label}</p>
      ))}
      <p className="text-xs text-slate-400">Calibration: four-point compatibility retained; not a certification of whole-pitch coverage.</p>
      {landmarkPreview && (
        <div className="rounded border border-slate-700 p-2 space-y-1">
          {landmarkPreview.measured === false || landmarkPreview.residualP95M == null ? (
            <p className="text-xs text-amber-200">Landmark residual unmeasured</p>
          ) : (
            <p className="text-xs text-amber-200">Preview landmark fit (p95 {landmarkPreview.residualP95M} m)</p>
          )}
          <p className="text-xs text-slate-400">{landmarkPreview.committed ? 'Committed' : 'Not committed'}</p>
          <p className="text-xs text-slate-500">Does not rerun image-space detection.</p>
          {onCommitCalibration && (
            <button
              type="button"
              onClick={() => onCommitCalibration({
                committed: Boolean(landmarkPreview.accepted),
                certified: false,
              })}
              className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white"
            >
              Commit calibration
            </button>
          )}
        </div>
      )}
      <label className="flex items-center gap-2 text-xs text-slate-400">
        <input type="checkbox" checked={cloud} onChange={(event) => setCloud(event.target.checked)} />
        Cloud permission
      </label>
      {onSavePolicy && <button type="button" disabled={liveSaving} onClick={() => void saveLive('policy')}
        className="rounded border border-slate-600 px-3 py-1 text-xs">Save cloud permission</button>}
      {liveMessage && <p role="status" className="text-xs text-amber-200">{liveMessage}</p>}
      {separateLiveSettings && <p className="text-xs text-slate-400">Save setup applies analytical settings only. Team names and current permissions have separate save actions and are never restored by undo.</p>}
      {onSave && (
        <button
          type="button"
          onClick={() => void handleSave()}
          disabled={saveState === 'pending'}
          className="px-3 py-1.5 rounded bg-emerald-700 text-xs font-semibold text-white disabled:opacity-50"
        >
          Save setup
        </button>
      )}
      {saveState === 'saved' && <p className="text-xs text-emerald-300">{separateLiveSettings ? 'Setup applied' : 'Setup saved'}</p>}
      {saveState === 'conflicted' && <p className="text-xs text-amber-200">{saveMessage ?? 'Setup save conflicted'}</p>}
      {manualTaggingPermitted && <p className="text-xs text-emerald-300">Manual tagging permitted.</p>}
      {!automationAdmitted && (
        <p className="text-xs text-amber-200">Rejected automation still permits tagging. Not a certification of the current implementation.</p>
      )}
      {cannotMeasure.length > 0 && (
        <p className="text-xs text-slate-500">Cannot measure: {cannotMeasure.join(', ')}</p>
      )}
    </section>
  );
}
