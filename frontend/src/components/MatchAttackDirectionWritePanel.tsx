import { useEffect, useState } from 'react';

import { postMatchAttackDirection } from '../utils/workbench';

interface MatchAttackDirectionWritePanelProps {
  matchId?: string;
}

export default function MatchAttackDirectionWritePanel({ matchId }: MatchAttackDirectionWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchAttackDirection(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.fromStoredConfig === true) {
          setNote('Posted attack direction does not send client mapping. Client left_to_right is not sent. fromStoredConfig stays true.');
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
    <section aria-label="Unmapped direction write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unmapped direction write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
