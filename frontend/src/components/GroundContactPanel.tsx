import { useEffect, useState } from 'react';

import { fetchGroundContact } from '../utils/workbench';

export default function GroundContactPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchGroundContact()
      .then((payload) => {
        if (cancelled) return;
        if (payload.boxCentreIsFoot === false) {
          setNote('Stored ground contact does not treat box centre as the foot.');
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
    <section aria-label="Stored ground contact" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored ground contact</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
