import { useState } from 'react';

import { postDecodeInterval } from '../utils/workbench';

export default function DecodeIntervalWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestInterval() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDecodeInterval();
      if (Array.isArray(payload.interval) && payload.interval[0] === 0 && payload.interval[1] === 0) {
        setNote('Posted decode interval keeps interval 0 to 0. Client proxy mapping is not sent. Proxy kind does not remap the interval.');
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
    <section aria-label="Unforced decode interval" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced decode interval</h4>
      <button
        type="button"
        aria-label="Request decode interval"
        onClick={() => void requestInterval()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request decode interval
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
