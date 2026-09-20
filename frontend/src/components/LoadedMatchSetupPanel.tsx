import { useEffect, useState } from 'react';

import SetupWizard, { type SetupWizardSavePayload } from './SetupWizard';
import { updateMatchConfig } from '../utils/api';
import { ApiError } from '../utils/request';
import { commandState, newCommandControls, type CommandControls, type CommandReceipt } from '../utils/commandLifecycle';
import { commitMatchCalibration, fetchLandmarkPreview, fetchMatchSetup, type LandmarkPreview, type MatchSetup } from '../utils/workbench';

export interface LoadedMatchSetupPanelProps {
  matchId?: string;
  generationId?: string;
  executeCommand?: (send: (controls: CommandControls) => Promise<CommandReceipt | undefined>, recovering?: boolean) => Promise<CommandReceipt | null>;
}

export default function LoadedMatchSetupPanel({ matchId, generationId, executeCommand }: LoadedMatchSetupPanelProps) {
  const [setup, setSetup] = useState<MatchSetup | null>(null);
  const [landmarkPreview, setLandmarkPreview] = useState<LandmarkPreview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    Promise.all([fetchMatchSetup(matchId, generationId), fetchLandmarkPreview(matchId, generationId)])
      .then(([payload, preview]) => {
        if (cancelled) return;
        setSetup(payload.certified === false ? payload : null);
        setLandmarkPreview(preview);
      }).catch((failure: unknown) => {
        if (!cancelled) { setSetup(null); setError(failure instanceof Error ? failure.message : 'Setup unavailable.'); }
      });
    return () => { cancelled = true; };
  }, [matchId, generationId]);

  async function apply(send: (controls: CommandControls) => Promise<CommandReceipt | undefined>) {
    const receipt = executeCommand ? await executeCommand(send)
      : await send(newCommandControls(generationId ?? setup?.generationId));
    if (!receipt || commandState(receipt) !== 'applied') throw new ApiError(
      receipt?.lastError ?? 'Setup was not applied. Check the correction status and refresh.', 409, 'COMMAND_NOT_APPLIED');
    return receipt;
  }

  async function handleSave(payload: SetupWizardSavePayload) {
    if (!matchId) throw new Error('Load a match first.');
    await apply(async (controls) => (await updateMatchConfig(matchId, {
      cameraProfile: payload.cameraProfile, pitchLengthM: payload.pitchLengthM, periods: payload.periods, ...controls,
    })).correction);
  }

  async function handleCommitCalibration() {
    if (!matchId || !landmarkPreview?.profile) return;
    setError(null);
    try {
      // A preview number is not a matrix or a holdout. Never invent calibration observations.
      await apply(async (controls) => (await commitMatchCalibration(matchId, { ...landmarkPreview.profile, ...controls })).correction);
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Calibration application unconfirmed.'); }
  }

  if (!setup) return error ? <p role="status" aria-label="Match setup unavailable" className="text-xs text-amber-200">{error}</p> : null;
  return (
    <>
      <SetupWizard matchId={matchId} cameraProfile={setup.cameraProfile}
        pitchLengthM={setup.pitchLengthM != null ? String(setup.pitchLengthM) : ''}
        homeTeam={setup.homeTeam ?? ''} awayTeam={setup.awayTeam ?? ''}
        cloudPermission={setup.cloudPermission === true}
        periods={setup.periods?.map((period) => period.name).join(',') || '1,2'} periodDefinitions={setup.periods}
        automationAdmitted={setup.automationAdmitted} manualTaggingPermitted={setup.manualTaggingPermitted}
        cannotMeasure={setup.cannotMeasure} landmarkPreview={landmarkPreview} onSave={handleSave} separateLiveSettings
        onSaveMetadata={async (payload) => { if (matchId) await updateMatchConfig(matchId, payload); }}
        onSavePolicy={async (rights) => { if (matchId) await updateMatchConfig(matchId, { rights }); }}
        onCommitCalibration={landmarkPreview?.profile && !landmarkPreview.committed ? () => { void handleCommitCalibration(); } : undefined}
      />
      {!landmarkPreview?.profile && <p className="text-xs text-amber-200">No measured calibration profile is available to commit. Supply actual source landmarks and independent holdouts; preview status alone is not calibration.</p>}
      {error && <p role="alert" className="text-xs text-amber-200">{error}</p>}
    </>
  );
}
