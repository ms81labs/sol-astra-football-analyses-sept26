import { useEffect, useState } from 'react';

import { fetchMetadataTargets } from '../utils/workbench';

export default function MetadataTargetsPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchMetadataTargets()
      .then((payload) => {
        if (cancelled) return;
        if (payload.measured === false && payload.doesNotPromiseVideoDecodeLatency === true) {
          setNote('Stored metadata targets are planning targets, not measurements. They do not promise video decode latency.');
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
    <section aria-label="Stored metadata targets" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored metadata targets</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
