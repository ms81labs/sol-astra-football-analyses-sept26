import { useEffect, useState } from 'react';

import { fetchMatchRates } from '../utils/workbench';

interface FourRatesPanelProps {
  matchId?: string;
}

export default function FourRatesPanel({ matchId }: FourRatesPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchRates(matchId)
      .then((payload) => {
        if (cancelled) return;
        const notes = payload.notes ?? [];
        if (
          payload.exportFpsEqualsInferenceFps === false
          && notes.includes('EXPORT_FPS_IS_NOT_INFERENCE_FPS')
        ) {
          setNote('Decode, detector, tracker and export are separate rates. Export fps is not inference fps.');
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
    <section aria-label="Four rates" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Four rates</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
