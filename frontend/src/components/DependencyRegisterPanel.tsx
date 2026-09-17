import { useEffect, useState } from 'react';

import { fetchDependencyRegister } from '../utils/workbench';

export default function DependencyRegisterPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchDependencyRegister()
      .then((payload) => {
        if (cancelled) return;
        if (
          payload.ultralytics?.fashionableOnly === false
          && payload.opencv?.fashionableOnly === false
          && payload.opencv.rollbackPath === 'fixture_frame_source'
        ) {
          setNote('Stored dependency register keeps fashionableOnly false. Client fashionableOnly true is not sent. OpenCV rollbackPath stays fixture_frame_source.');
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
    <section aria-label="Stored dependency register" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored dependency register</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
