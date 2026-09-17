import { useEffect, useState } from 'react';

import SetupWizard, { type SetupWizardSavePayload } from './SetupWizard';
import { updateMatchConfig } from '../utils/api';
import {
  commitMatchCalibration,
  fetchLandmarkPreview,
  fetchMatchSetup,
  type LandmarkPreview,
  type MatchSetup,
} from '../utils/workbench';

interface LoadedMatchSetupPanelProps {
  matchId?: string;
}

export default function LoadedMatchSetupPanel({ matchId }: LoadedMatchSetupPanelProps) {
  const [setup, setSetup] = useState<MatchSetup | null>(null);
  const [landmarkPreview, setLandmarkPreview] = useState<LandmarkPreview | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    Promise.all([fetchMatchSetup(matchId), fetchLandmarkPreview(matchId)])
      .then(([payload, preview]) => {
        if (cancelled) return;
        if (payload.certified === false) {
          setSetup(payload);
          setLandmarkPreview(preview);
        } else {
          setSetup(null);
          setLandmarkPreview(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSetup(null);
          setLandmarkPreview(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [matchId]);

  async function handleSave(payload: SetupWizardSavePayload) {
    if (!matchId) return;
    await updateMatchConfig(matchId, {
      cameraProfile: payload.cameraProfile,
      pitchLengthM: payload.pitchLengthM,
      periods: payload.periods,
      rights: payload.rights,
      homeTeam: payload.homeTeam,
      awayTeam: payload.awayTeam,
    });
  }

  async function handleCommitCalibration() {
    if (!matchId) return;
    const result = await commitMatchCalibration(matchId, {
      calibrationId: `${matchId}-live`,
      cameraModel: 'planar_homography',
      residualP95M: landmarkPreview?.residualP95M ?? null,
      landmarks: landmarkPreview?.accepted
        ? [{ name: 'holdout', imageX: 10, imageY: 10, pitchX: 10, pitchY: 10, independentHoldout: true }]
        : [{ name: 'corner', imageX: 0, imageY: 0, pitchX: 0, pitchY: 0, independentHoldout: false }],
      homography: landmarkPreview?.accepted
        ? [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        : undefined,
    });
    setLandmarkPreview((current) => current
      ? { ...current, committed: result.committed, accepted: result.committed, certified: result.certified }
      : { residualP95M: null, accepted: result.committed, committed: result.committed });
    setSetup((current) => current ? { ...current, calibrationCommitted: result.committed } : current);
  }

  if (!setup) return null;
  return (
    <SetupWizard
      matchId={matchId}
      cameraProfile={setup.cameraProfile}
      pitchLengthM={setup.pitchLengthM != null ? String(setup.pitchLengthM) : ''}
      homeTeam={setup.homeTeam ?? ''}
      awayTeam={setup.awayTeam ?? ''}
      automationAdmitted={setup.automationAdmitted}
      manualTaggingPermitted={setup.manualTaggingPermitted}
      cannotMeasure={setup.cannotMeasure}
      landmarkPreview={landmarkPreview}
      onSave={handleSave}
      onCommitCalibration={() => { void handleCommitCalibration(); }}
    />
  );
}
