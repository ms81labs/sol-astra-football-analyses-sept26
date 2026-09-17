import { useState } from 'react';

import { postDecodeSample } from '../utils/workbench';

export default function DecodeSampleWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestSample() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDecodeSample();
      if (payload.targetFpsEqualsInferenceFps === false) {
        setNote('Posted decode sample keeps targetFpsEqualsInferenceFps false. Client exported true is not sent. Sample mapping does not prove inference fps.');
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
    <section aria-label="Unforced decode sample" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced decode sample</h4>
      <button
        type="button"
        aria-label="Request decode sample"
        onClick={() => void requestSample()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request decode sample
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
