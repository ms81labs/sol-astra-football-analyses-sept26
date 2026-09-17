import { useState } from 'react';

import { postGroundContact } from '../utils/workbench';

export default function GroundContactWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestContact() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postGroundContact();
      if (payload.boxCentreIsFoot === false && payload.airborne === false) {
        setNote('Posted ground contact keeps boxCentreIsFoot false. Client POST airborne true is not sent. Posted contact stays a foot estimate, not box centre.');
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
    <section aria-label="Unforced ground contact" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced ground contact</h4>
      <button
        type="button"
        aria-label="Request ground contact"
        onClick={() => void requestContact()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request ground contact
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
