import { useEffect, useState } from 'react';

import { fetchResidencyClaim } from '../utils/workbench';

export default function ResidencyClaimPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchResidencyClaim()
      .then((payload) => {
        if (cancelled) return;
        if (payload.euProcessingProven === false) {
          setNote('Stored residency claim does not prove EU processing. Requested region is not proof.');
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
    <section aria-label="Stored residency claim" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored residency claim</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
