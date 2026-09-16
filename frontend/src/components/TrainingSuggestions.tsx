interface TrainingObservation {
  id: string;
  label: string;
}

interface TrainingDrill {
  name: string;
  coachReviewed?: boolean;
}

interface TrainingSuggestionsProps {
  observations?: TrainingObservation[];
  drills?: TrainingDrill[];
}

export default function TrainingSuggestions({
  observations = [],
  drills = [],
}: TrainingSuggestionsProps) {
  return (
    <section aria-label="Training suggestions" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Training suggestions</h4>
      <p className="text-xs text-slate-400">Accepted observations combined with a coach-reviewed drill library.</p>
      <ul className="space-y-1 text-xs text-slate-300">
        {drills.map((drill) => (
          <li key={drill.name}>{drill.name}</li>
        ))}
      </ul>
      {observations.map((observation) => (
        <p key={observation.id} className="text-xs text-slate-400">{observation.label}</p>
      ))}
      <p className="text-xs text-slate-500">
        Does not prescribe medical load, diagnose fatigue, or infer injury from tracking.
      </p>
    </section>
  );
}
