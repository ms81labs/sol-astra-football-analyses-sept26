import { useState } from 'react';

import { postLeftoverSignedAccess } from '../utils/workbench';

export default function LeftoverSignedAccessWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestSignedAccess() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postLeftoverSignedAccess();
      if (
        payload.admitted === false
        && payload.reasonCodes?.includes('UNSIGNED_OR_UNSCOPED_OBJECT_ACCESS')
      ) {
        setNote('Posted leftover signed object access keeps admitted false. Client POST token is not sent. Posted UNSIGNED_OR_UNSCOPED_OBJECT_ACCESS stays blocking.');
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
    <section aria-label="Unforced leftover signed access" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover signed access</h4>
      <button
        type="button"
        aria-label="Request leftover signed access"
        onClick={() => void requestSignedAccess()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover signed access
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
