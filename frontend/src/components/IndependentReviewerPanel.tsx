import { useEffect, useState } from 'react';

import { fetchIndependentReviewer } from '../utils/workbench';

export default function IndependentReviewerPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchIndependentReviewer()
      .then((payload) => {
        if (cancelled) return;
        if (payload.accepted === false && (payload.reasonCodes ?? []).includes('REVIEWER_NOT_INDEPENDENT')) {
          setNote('Stored independent reviewer stays unaccepted. REVIEWER_NOT_INDEPENDENT stays blocking. Held-out predictions stay uninspected.');
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
    <section aria-label="Stored independent reviewer" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored independent reviewer</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
