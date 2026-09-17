import { useEffect, useState } from 'react';

import { fetchTrainingDrills } from '../utils/workbench';

export default function TrainingDrillsPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchTrainingDrills()
      .then((payload) => {
        if (cancelled) return;
        if (payload.prescribesMedicalLoad === false && payload.diagnosesFatigueOrInjury === false) {
          setNote('Stored training drills keep medical load unprescribed. Fatigue and injury stay undiagnosed from tracking.');
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
    <section aria-label="Stored training drills" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored training drills</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
