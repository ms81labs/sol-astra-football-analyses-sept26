import { useEffect, useState } from 'react';

import { fetchPreemptible } from '../utils/workbench';

export default function PreemptiblePolicyPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchPreemptible()
      .then((payload) => {
        if (cancelled) return;
        if (payload.allowed === false) {
          setNote('Stored preemptible policy stays disallowed. Missing checkpoints do not admit workers.');
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
    <section aria-label="Stored preemptible policy" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored preemptible policy</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
