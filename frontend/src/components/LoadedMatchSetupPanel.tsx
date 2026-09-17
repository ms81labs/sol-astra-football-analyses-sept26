import { useEffect, useState } from 'react';

import SetupWizard from './SetupWizard';
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

  if (!setup) return null;
  return (
    <SetupWizard
      cameraProfile={setup.cameraProfile}
      pitchLengthM={setup.pitchLengthM != null ? String(setup.pitchLengthM) : ''}
      automationAdmitted={setup.automationAdmitted}
      manualTaggingPermitted={setup.manualTaggingPermitted}
      cannotMeasure={setup.cannotMeasure}
    />
  );
}
