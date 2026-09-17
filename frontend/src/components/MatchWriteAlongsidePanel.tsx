import { useEffect, useState } from 'react';

import { writeMatchAlongside } from '../utils/workbench';

interface MatchWriteAlongsidePanelProps {
  matchId?: string;
}

export default function MatchWriteAlongsidePanel({ matchId }: MatchWriteAlongsidePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    writeMatchAlongside(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.mutatedHistorical === false && payload.digest !== payload.previousDigest) {
          setNote('Write-alongside artifacts do not mutate historical output. mutatedHistorical is false. Digest is not the previous digest.');
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
    <section aria-label="Write-alongside artifacts" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Write-alongside artifacts</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
