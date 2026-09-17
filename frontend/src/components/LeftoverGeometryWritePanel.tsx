import { useState } from 'react';

import { postLeftoverGeometry } from '../utils/workbench';

export default function LeftoverGeometryWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestGeometry() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postLeftoverGeometry();
      if (
        payload.evaluation?.accepted === false
        && payload.evaluation.reasonCodes?.includes('CALIBRATION_UNAVAILABLE')
      ) {
        setNote('Posted leftover geometry keeps evaluation.accepted false. Client POST accepted true is not sent. Posted four corners stay CALIBRATION_UNAVAILABLE.');
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
    <section aria-label="Unforced leftover geometry" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover geometry</h4>
      <button
        type="button"
        aria-label="Request leftover geometry"
        onClick={() => void requestGeometry()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover geometry
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
