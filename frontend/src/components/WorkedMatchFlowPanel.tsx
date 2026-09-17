import { useEffect, useState } from 'react';

import { fetchWorkedMatchFlow } from '../utils/workbench';

export default function WorkedMatchFlowPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchWorkedMatchFlow()
      .then((payload) => {
        if (cancelled) return;
        if (payload.illustrative === true && payload.correctionInvalidatesReportWithoutRerun === true) {
          setNote('Stored worked match flow stays illustrative. A correction invalidates the report without a rerun.');
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
    <section aria-label="Stored worked match flow" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored worked match flow</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
