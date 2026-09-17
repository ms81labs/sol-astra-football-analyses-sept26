import { useEffect, useState } from 'react';

import { fetchArchitectureDecisions } from '../utils/workbench';

export default function ArchitectureDecisionsPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchArchitectureDecisions()
      .then((payload) => {
        if (cancelled) return;
        const release = (payload.items ?? []).find((item) => item.id === 'capability_release');
        if (release?.decision === 'independent_gates_not_merged_files' && release.reversible === true) {
          setNote('Stored architecture decisions keep independent gates, not merged files. Capability release stays reversible.');
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
  }, []);

  if (!note) return null;
  return (
    <section aria-label="Stored architecture decisions" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored architecture decisions</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
