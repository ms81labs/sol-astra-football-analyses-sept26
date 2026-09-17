import { useEffect, useState } from 'react';

import { fetchMatchShotFeatures } from '../utils/workbench';

interface MatchShotFeaturesPanelProps {
  matchId?: string;
}

export default function MatchShotFeaturesPanel({ matchId }: MatchShotFeaturesPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchShotFeatures(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.imputedAsCalibrated === false) {
          setNote('Missing shot features are not imputed as calibrated xG. imputedAsCalibrated is false.');
        } else {
          setNote(null);
        }
      })
      .catch(() => {
        if (!cancelled) setNote(null);
      });
    return () => {
      cancelled = true;
    };
  }, [matchId]);

  if (!note) return null;
  return (
    <section aria-label="Shot features" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Shot features</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
