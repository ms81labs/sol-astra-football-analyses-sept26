import { useState } from 'react';

import { postAssistanceSelectEvidence } from '../utils/workbench';

export default function AssistanceSelectEvidenceWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestSelect() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postAssistanceSelectEvidence();
      if (payload.accepted === true && (payload.evidence ?? []).length === 0) {
        setNote('Posted assistance select-evidence keeps accepted true. Client claimedIds are not sent. Empty claimed ids stay selected.');
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
    <section aria-label="Unforced assistance select-evidence" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced assistance select-evidence</h4>
      <button
        type="button"
        aria-label="Request assistance select-evidence"
        onClick={() => void requestSelect()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request assistance select-evidence
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
