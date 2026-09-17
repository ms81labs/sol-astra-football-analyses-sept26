import { useEffect, useState } from 'react';

import { postMatchFormation } from '../utils/workbench';

interface MatchFormationWritePanelProps {
  matchId?: string;
}

export default function MatchFormationWritePanel({ matchId }: MatchFormationWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchFormation(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.availability === 'withheld' && payload.value == null) {
          setNote('Posted formation ignores client 4-3-3. Availability stays withheld. value stays unpublished.');
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
  }, [matchId]);

  if (!note) return null;
  return (
    <section aria-label="Uninvented shape write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Uninvented shape write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
