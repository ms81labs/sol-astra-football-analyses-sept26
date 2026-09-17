import { useEffect, useState } from 'react';

import { fetchTrainingSampling } from '../utils/workbench';

export default function TrainingSamplingPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchTrainingSampling()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.uncertaintyOnly === false
          && payload.mix?.includes('random_representative')
        ) {
          setNote('Stored training sampling keeps uncertaintyOnly false. Mix includes random_representative. Uncertainty sampling is not the only training source.');
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
    <section aria-label="Stored training sampling" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored training sampling</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
