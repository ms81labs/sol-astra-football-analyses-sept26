import { useEffect, useState } from 'react';

import { postMatchPackage } from '../utils/workbench';

interface MatchPackageWritePanelProps {
  matchId?: string;
}

export default function MatchPackageWritePanel({ matchId }: MatchPackageWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchPackage(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.operator?.secretsAdmitted === true) {
          setNote('Posted package write ignores client events and secrets. Client DAYTONA_API_KEY is not sent. secretsAdmitted stays true.');
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
    <section aria-label="Uninjected operator write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Uninjected operator write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
