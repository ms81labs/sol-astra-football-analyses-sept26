import { useEffect, useState } from 'react';

import SetupWizard, { type SetupWizardSavePayload } from './SetupWizard';
import { updateMatchConfig } from '../utils/api';
import { fetchMatchSetup, type MatchSetup } from '../utils/workbench';

interface LoadedMatchSetupPanelProps {
  matchId?: string;
}

export default function LoadedMatchSetupPanel({ matchId }: LoadedMatchSetupPanelProps) {
  const [setup, setSetup] = useState<MatchSetup | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchSetup(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.certified === false) {
          setSetup(payload);
        } else {
          setSetup(null);
        }
      })
      .catch(() => {
        if (!cancelled) setSetup(null);
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
    });
  }

  if (!setup) return null;
  return (
    <SetupWizard
      matchId={matchId}
      cameraProfile={setup.cameraProfile}
      pitchLengthM={setup.pitchLengthM != null ? String(setup.pitchLengthM) : ''}
      automationAdmitted={setup.automationAdmitted}
      manualTaggingPermitted={setup.manualTaggingPermitted}
      cannotMeasure={setup.cannotMeasure}
      onSave={handleSave}
    />
  );
}
