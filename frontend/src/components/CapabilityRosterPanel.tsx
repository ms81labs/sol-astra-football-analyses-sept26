import { useEffect, useState } from 'react';

import { fetchCapabilityRoster } from '../utils/workbench';

export default function CapabilityRosterPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchCapabilityRoster()
      .then((payload) => {
        if (cancelled) return;
        const capabilities = payload.capabilities ?? [];
        const playerAttribution = capabilities.find((item) => item.id === 'player_attribution');
        const physicalMetrics = capabilities.find((item) => item.id === 'physical_metrics');
        if (playerAttribution?.status === 'unproven' && physicalMetrics?.status === 'unavailable') {
          setNote('Stored capability roster keeps player_attribution unproven. physical_metrics stay unavailable. Listing a capability is not independent accuracy.');
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
    <section aria-label="Stored capability roster" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored capability roster</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
