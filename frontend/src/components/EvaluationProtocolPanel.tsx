import { useEffect, useState } from 'react';

import { fetchStoredEvaluationProtocol } from '../utils/workbench';

export default function EvaluationProtocolPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchStoredEvaluationProtocol()
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.reasonCodes ?? [];
        if (
          payload.accepted === false
          && payload.completeTasks === 0
          && payload.protocolVersion === 'football_analysis_pilot_labels_v3'
          && reasons.includes('LABELS_INCOMPLETE')
        ) {
          setNote('Frozen protocol football_analysis_pilot_labels_v3 remains unaccepted. LABELS_INCOMPLETE. completeTasks stays 0.');
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
    <section aria-label="Stored frozen protocol" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored frozen protocol</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
