import { useEffect, useState } from 'react';

import { fetchSignedObjectAccess } from '../utils/workbench';

export default function SignedObjectAccessPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchSignedObjectAccess()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.admitted === false
          && payload.reasonCodes?.includes('UNSIGNED_OR_UNSCOPED_OBJECT_ACCESS')
        ) {
          setNote('Stored signed object access keeps admitted false. UNSIGNED_OR_UNSCOPED_OBJECT_ACCESS stays blocking. A missing token is not scoped object admission.');
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
    <section aria-label="Stored signed object access" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored signed object access</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
