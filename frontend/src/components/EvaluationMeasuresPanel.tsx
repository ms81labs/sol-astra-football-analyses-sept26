import { useEffect, useState } from 'react';

import { fetchEvaluationMeasures } from '../utils/workbench';

export default function EvaluationMeasuresPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchEvaluationMeasures()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.trackevalIsGroundTruth === false
          && payload.annotationServiceHealthSatisfiesLabelGate === false
        ) {
          setNote('Stored evaluation measures do not treat TrackEval as ground truth. Annotation service health does not satisfy the label gate.');
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
    <section aria-label="Stored evaluation measures" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored evaluation measures</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
