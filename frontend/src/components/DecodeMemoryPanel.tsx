import { useEffect, useState } from 'react';

import { fetchDecodeMemory } from '../utils/workbench';

export default function DecodeMemoryPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchDecodeMemory()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.gpuResident === false
          && payload.retainAllDecodedFrames === false
          && payload.canPromoteDefault === false
        ) {
          setNote('Stored decode memory stays non-resident on GPU. Decoded frames are not retained. Hardware decode does not promote a GPU default.');
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
    <section aria-label="Stored decode memory" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored decode memory</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
