import { useEffect, useState } from 'react';

import { fetchMatchProvenance } from '../utils/workbench';

interface MatchProvenancePanelProps {
  matchId?: string;
}

export default function MatchProvenancePanel({ matchId }: MatchProvenancePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchProvenance(matchId)
      .then((payload) => {
        if (cancelled) return;
        const reasons = payload.reasonCodes ?? [];
        const missing = payload.missingEvidenceIds ?? [];
        if (payload.accepted === true && !reasons.includes('FABRICATED_EVIDENCE') && missing.length === 0) {
          setNote('Published claims lead back to stored evidence.');
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
    <section aria-label="Report provenance" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Report provenance</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
