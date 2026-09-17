import { useEffect, useState } from 'react';

import { fetchStoredReleaseDossier } from '../utils/workbench';

export default function ReleaseDossierPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchStoredReleaseDossier()
      .then((payload) => {
        if (cancelled) return;
        if (payload.nativeCode === 'gated_inert' && payload.deploymentBoundary === 'loopback') {
          setNote('Stored release dossier keeps nativeCode gated_inert. deploymentBoundary stays loopback. Client nativeCode approved is not sent.');
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
    <section aria-label="Stored release dossier" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored release dossier</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
