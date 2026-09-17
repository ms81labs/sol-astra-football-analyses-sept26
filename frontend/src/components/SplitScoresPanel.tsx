import { useEffect, useState } from 'react';

import { fetchSplitScores } from '../utils/workbench';

export default function SplitScoresPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchSplitScores()
      .then((payload) => {
        if (cancelled) return;
        if (payload.detectorScore === null && payload.calibratedProbability === null) {
          setNote('Stored split scores keep detectorScore null. calibratedProbability stays null. A detector score is not a calibrated probability.');
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
  }, []);

  if (!note) return null;
  return (
    <section aria-label="Stored split scores" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored split scores</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
