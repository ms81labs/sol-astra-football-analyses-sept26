import { useEffect, useState } from 'react';

import { fetchCollaborationLock } from '../utils/workbench';

export default function CollaborationLockPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchCollaborationLock()
      .then((payload) => {
        if (cancelled) return;
        if (payload.hosted?.admitted === false && payload.hosted?.silentlyReplaced === false) {
          setNote('Stored collaboration lock keeps hosted mode unadmitted. Locks are not silently replaced.');
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
    <section aria-label="Stored collaboration lock" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored collaboration lock</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
