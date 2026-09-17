import { useState } from 'react';

import { postReleaseDossier } from '../utils/workbench';

export default function ReleaseDossierWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestDossier() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postReleaseDossier();
      if (payload.nativeCode === 'gated_inert' && payload.deploymentBoundary === 'loopback') {
        setNote('Posted release dossier keeps nativeCode gated_inert. Client POST nativeCode approved is not sent. Posted deploymentBoundary stays loopback.');
      } else {
        setNote(null);
      }
    } catch {
      setNote(null);
    } finally {
      setPending(false);
    }
  }

  return (
    <section aria-label="Unforced release dossier" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced release dossier</h4>
      <button
        type="button"
        aria-label="Request release dossier"
        onClick={() => void requestDossier()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request release dossier
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
