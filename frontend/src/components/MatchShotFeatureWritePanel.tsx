import { useEffect, useState } from 'react';

import { postMatchShotFeatures } from '../utils/workbench';

interface MatchShotFeatureWritePanelProps {
  matchId?: string;
}

export default function MatchShotFeatureWritePanel({ matchId }: MatchShotFeatureWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchShotFeatures(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.imputedAsCalibrated === false) {
          setNote('Posted shot features ignore client goal rows. Client shots are not sent. imputedAsCalibrated stays false.');
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
    <section aria-label="Unimputed feature write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unimputed feature write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
