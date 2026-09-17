import { useEffect, useState } from 'react';

import { fetchSupportBundle } from '../utils/workbench';

export default function SupportBundlePanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchSupportBundle()
      .then((payload) => {
        if (cancelled) return;
        if (payload.released === false && (payload.reasonCodes ?? []).includes('CONSENT_REQUIRED')) {
          setNote('Stored support bundle stays unreleased. Client consented true is ignored. CONSENT_REQUIRED stays blocking.');
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
    <section aria-label="Stored support bundle" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored support bundle</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
