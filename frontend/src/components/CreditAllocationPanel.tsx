import { useEffect, useState } from 'react';

import { fetchCreditAllocation } from '../utils/workbench';

export default function CreditAllocationPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchCreditAllocation()
      .then((payload) => {
        if (cancelled) return;
        if (payload.authorised === false && payload.gpuCreditsDoNotPayForLabels === true) {
          setNote('Stored credit allocation is unauthorised. GPU credits do not pay for independent labels.');
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
    <section aria-label="Stored credit allocation" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored credit allocation</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
