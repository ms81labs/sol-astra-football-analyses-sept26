import { useEffect, useState } from 'react';

import { fetchOperatorHandoff } from '../utils/workbench';

export default function OperatorHandoffPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchOperatorHandoff()
      .then((payload) => {
        if (cancelled) return;
        if (payload.schemaVersion === 'video_to_analysis_operator_handoff_view_model_v1') {
          setNote('Stored operator handoff is historical. Historical operator-handoff is not current-source sealed inference. Current-source labels stay 0 of 18.');
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
    <section aria-label="Stored operator handoff" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored operator handoff</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
