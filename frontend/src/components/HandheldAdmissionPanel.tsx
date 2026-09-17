import { useEffect, useState } from 'react';

import { fetchHandheldAdmission } from '../utils/workbench';

export default function HandheldAdmissionPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchHandheldAdmission()
      .then((payload) => {
        if (cancelled) return;
        if (payload.certified === false && (payload.withhold ?? []).includes('physical_metrics')) {
          setNote('Stored handheld admission is not certified. physical_metrics stay on the withhold list.');
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
    <section aria-label="Stored handheld admission" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored handheld admission</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
