import { useState } from 'react';

import { postSharing } from '../utils/workbench';

export default function SharingWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestSharing() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postSharing();
      if (payload.expiredAtNow === true && payload.expiredAtTtl === true) {
        setNote('Posted sharing keeps expiredAtNow true. Client expired false is not sent. Empty TTL stays expired.');
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
    <section aria-label="Unforced sharing" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced sharing</h4>
      <button
        type="button"
        aria-label="Request sharing"
        onClick={() => void requestSharing()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request sharing
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
