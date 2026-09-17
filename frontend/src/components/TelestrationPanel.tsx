import { useEffect, useState } from 'react';

import { fetchTelestration } from '../utils/workbench';

export default function TelestrationPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchTelestration()
      .then((payload) => {
        if (cancelled) return;
        if (payload.blenderEnabled === false && payload.pitchView === '2d') {
          setNote('Stored telestration keeps blenderEnabled false. Pitch view stays 2d. Blender is not admitted as 3D overlay.');
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
    <section aria-label="Stored telestration" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored telestration</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
