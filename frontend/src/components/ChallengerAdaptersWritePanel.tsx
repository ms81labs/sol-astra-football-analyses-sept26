import { useState } from 'react';

import { postChallengerAdapters } from '../utils/workbench';

export default function ChallengerAdaptersWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestChallengers() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postChallengerAdapters();
      if (
        payload.kloppy?.enabled === false
        && payload.roboflow?.enabled === false
        && payload.mcbyte?.enabled === false
      ) {
        setNote('Posted challenger adapters keep kloppy.enabled false. Client POST kloppy true is not sent. Posted adapters stay unadmitted.');
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
    <section aria-label="Unforced challenger adapters" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced challenger adapters</h4>
      <button
        type="button"
        aria-label="Request challenger adapters"
        onClick={() => void requestChallengers()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request challenger adapters
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
