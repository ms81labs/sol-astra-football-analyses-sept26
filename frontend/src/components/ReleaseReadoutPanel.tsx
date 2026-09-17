import { useEffect, useState } from 'react';

import { fetchReleaseReadout } from '../utils/workbench';

export default function ReleaseReadoutPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchReleaseReadout()
      .then((payload) => {
        if (cancelled) return;
        if (payload.schemaVersion === 'video_to_analysis_release_readout_view_model_v1') {
          setNote('Stored release readout is historical. Historical release-readout is not current-source sealed inference. Independent labels stay unaccepted.');
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
    <section aria-label="Stored release readout" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored release readout</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
