import { useEffect, useState } from 'react';

import { fetchDistributedBroker } from '../utils/workbench';

export default function DistributedBrokerPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchDistributedBroker()
      .then((payload) => {
        if (cancelled) return;
        if (payload.admitted === false && payload.renamesCurrentQueue === false) {
          setNote('Stored distributed broker stays unadmitted. It does not rename the current queue.');
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
    <section aria-label="Stored distributed broker" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored distributed broker</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
