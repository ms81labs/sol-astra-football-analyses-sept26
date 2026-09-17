import { useEffect, useState } from 'react';

import { fetchRiskRegister } from '../utils/workbench';

export default function RiskRegisterPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchRiskRegister()
      .then((payload) => {
        if (cancelled) return;
        const incomplete = (payload.items ?? []).some((item) => item.id === 'labels_incomplete');
        if (incomplete) {
          setNote('Stored risk register keeps labels_incomplete as a live risk. Service checks are not locked labels.');
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
    <section aria-label="Stored risk register" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored risk register</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
