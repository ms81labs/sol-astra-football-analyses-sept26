import { useState } from 'react';

import { postLeftoverTrainingAdmit } from '../utils/workbench';

export default function LeftoverTrainingAdmitWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestAdmit() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postLeftoverTrainingAdmit();
      if (
        payload.admitted === false
        && payload.reasonCodes?.includes('LOCKED_EVALUATION_ISOLATION')
      ) {
        setNote('Posted leftover training admit keeps admitted false. Client POST rights granted is not sent. Posted leftover admit stays LOCKED_EVALUATION_ISOLATION.');
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
    <section aria-label="Unforced leftover training admit" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover training admit</h4>
      <button
        type="button"
        aria-label="Request leftover training admit"
        onClick={() => void requestAdmit()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover training admit
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
