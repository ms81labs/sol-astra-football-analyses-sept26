import { useEffect, useState } from 'react';

import { fetchMatchCoverage } from '../utils/workbench';

interface MatchCoveragePanelProps {
  matchId?: string;
}

export default function MatchCoveragePanel({ matchId }: MatchCoveragePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchCoverage(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.coverageAware === true && payload.representsWholeMatch === false) {
          setNote('This report is coverage-aware and does not represent the whole match.');
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
    <section aria-label="Report coverage" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Report coverage</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
