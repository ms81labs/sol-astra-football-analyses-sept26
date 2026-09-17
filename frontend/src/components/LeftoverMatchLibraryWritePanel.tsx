import { useState } from 'react';

import { postLeftoverMatchLibrary } from '../utils/workbench';

export default function LeftoverMatchLibraryWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestLibrary() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postLeftoverMatchLibrary();
      if (Array.isArray(payload.results) && payload.results.length === 0) {
        setNote('Posted leftover match library keeps results empty. Client POST forged matches are not sent. Posted leftover match library is not match-scoped queries.');
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
    <section aria-label="Unforced leftover match library" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover match library</h4>
      <button
        type="button"
        aria-label="Request leftover match library"
        onClick={() => void requestLibrary()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover match library
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
