import { useEffect, useState } from 'react';

import { fetchMatchAttackDirection } from '../utils/workbench';

interface MatchAttackDirectionPanelProps {
  matchId?: string;
}

export default function MatchAttackDirectionPanel({ matchId }: MatchAttackDirectionPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchAttackDirection(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.fromStoredConfig === true) {
          setNote('Stored attack direction comes from match config. fromStoredConfig is true. Client mapping is ignored.');
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
    <section aria-label="Stored attack direction" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored attack direction</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
