import { useState } from 'react';

import { postDependencyRegister } from '../utils/workbench';

export default function DependencyRegisterWritePanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestDependencies() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await postDependencyRegister();
      if (
        payload.ultralytics?.fashionableOnly === false
        && payload.opencv?.fashionableOnly === false
        && payload.opencv.rollbackPath === 'fixture_frame_source'
      ) {
        setNote('Posted dependency register keeps fashionableOnly false. Client POST fashionableOnly true is not sent. Posted OpenCV rollbackPath stays fixture_frame_source.');
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
    <section aria-label="Unforced dependency register" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced dependency register</h4>
      <button
        type="button"
        aria-label="Request dependency register"
        onClick={() => void requestDependencies()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request dependency register
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
