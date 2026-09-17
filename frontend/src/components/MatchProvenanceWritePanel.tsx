import { useEffect, useState } from 'react';

import { postMatchProvenance } from '../utils/workbench';

interface MatchProvenanceWritePanelProps {
  matchId?: string;
}

export default function MatchProvenanceWritePanel({ matchId }: MatchProvenanceWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    postMatchProvenance(matchId)
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.reasonCodes ?? [];
        if (payload.accepted === true && !reasons.includes('FABRICATED_EVIDENCE')) {
          setNote('Posted provenance ignores client fabricated-evidence. Client knownEvidenceIds are not sent. leftover /api/reports/assemble stays unused.');
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
    <section aria-label="Unclaimed evidence write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unclaimed evidence write</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
