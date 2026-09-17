import { useEffect, useState } from 'react';

import { fetchStoredDecodeFrames } from '../utils/workbench';

export default function DecodeFramesPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchStoredDecodeFrames()
      .then((payload) => {
        if (cancelled) return;
        if (payload.backend === 'fixture' && payload.gpuPromoted === false && payload.pyavDefault === false) {
          setNote('Stored decode frames keep backend fixture. gpuPromoted stays false. Client pyav cuda frames are not sent.');
        } else {
          setNote(null);
        }
      })
      .catch(() => {
        if (!cancelled) setNote(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!note) return null;
  return (
    <section aria-label="Stored decode frames" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored decode frames</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
