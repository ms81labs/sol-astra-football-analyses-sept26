import { useEffect, useState } from 'react';

import { importMatchRecovery } from '../utils/workbench';

interface MatchRecoveryImportPanelProps {
  matchId?: string;
}

export default function MatchRecoveryImportPanel({ matchId }: MatchRecoveryImportPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    importMatchRecovery(matchId)
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.reasonCodes ?? [];
        if (payload.accepted === false && reasons.includes('CORRUPTED_ARTIFACT')) {
          setNote('SHA-mismatch recovery import is not accepted. CORRUPTED_ARTIFACT. Client expectedSha256 cannot force admission.');
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
    <section aria-label="Corrupted recovery import" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Corrupted recovery import</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
