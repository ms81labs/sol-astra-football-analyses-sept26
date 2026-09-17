import { useState } from 'react';

import { postSplitScores } from '../utils/workbench';

export default function SplitScoresWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestScores() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postSplitScores();
      if (payload.detectorScore == null && payload.calibratedProbability == null) {
        setNote('Posted split scores keep detectorScore null. Client POST detectorScore 0.81 is not sent. Posted calibratedProbability stays null.');
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
    <section aria-label="Unforced split scores" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced split scores</h4>
      <button
        type="button"
        aria-label="Request split scores"
        onClick={() => void requestScores()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request split scores
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
