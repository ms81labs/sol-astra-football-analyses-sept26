import { useEffect, useState } from 'react';

import { fetchHeldOutQuestions } from '../utils/workbench';

export default function HeldOutQuestionsPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchHeldOutQuestions()
      .then((payload) => {
        if (cancelled) return;
        const tired = (payload.questions ?? []).find((question) => (
          (question.text ?? '').includes('tired was player 7')
          && question.unanswerable === true
        ));
        if (tired) {
          setNote('Stored held-out questions keep fatigue unanswerable. The 89th-minute tired query is not inferred.');
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
    <section aria-label="Stored held-out questions" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored held-out questions</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
