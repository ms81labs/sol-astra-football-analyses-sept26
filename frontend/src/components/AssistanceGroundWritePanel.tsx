import { useState } from 'react';

import { postAssistanceGround } from '../utils/workbench';

export default function AssistanceGroundWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestGround() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postAssistanceGround();
      if (payload.route === 'template' && (payload.reasonCodes ?? []).includes('GROUNDED')) {
        setNote('Posted assistance ground keeps route template. Client evidence is not sent. Empty claimed ids stay grounded.');
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
    <section aria-label="Unforced assistance ground" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced assistance ground</h4>
      <button
        type="button"
        aria-label="Request assistance ground"
        onClick={() => void requestGround()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request assistance ground
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
