import { useEffect, useState } from 'react';

import { fetchMatchProxy } from '../utils/workbench';

interface ProxyAssetsPanelProps {
  matchId?: string;
}

export default function ProxyAssetsPanel({ matchId }: ProxyAssetsPanelProps) {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchProxy(matchId)
      .then((payload) => {
        if (cancelled) return;
        const assets = payload.assets;
        const hasDerived = Boolean(assets?.proxy && assets?.thumbnails && assets?.waveform);
        if (
          payload.replacesOriginal === false
          && payload.originalRetained === true
          && Array.isArray(payload.ptsMap)
          && hasDerived
        ) {
          setNote('Derived browsing proxy, thumbnails and waveform retain the original. Original-to-proxy presentation time is mapped. The proxy does not replace the original source.');
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
    <section aria-label="Derived proxy assets" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Derived proxy assets</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
