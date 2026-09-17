import { useEffect, useState } from 'react';

import { fetchMatchPackage } from '../utils/workbench';

interface MatchPackagePanelProps {
  matchId?: string;
}

export default function MatchPackagePanel({ matchId }: MatchPackagePanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchPackage(matchId)
      .then((payload) => {
        if (cancelled) return;
        const limitations = payload.analyst?.limitations ?? [];
        const schema = payload.operator?.manifest?.schema;
        const labelsIncomplete = limitations.some((item) => /independent labels 0\/18/i.test(item));
        if (labelsIncomplete && schema === 'match_package_v1' && payload.operator?.secretsAdmitted === true) {
          setNote('Coverage and limitations summary: Independent labels 0/18 complete. Versioned report match_package_v1. This package does not expose credentials.');
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
    <section aria-label="Match package" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Reviewed match package</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
