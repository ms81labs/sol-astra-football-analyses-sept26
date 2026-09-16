interface TeamCluster {
  id: number | string;
  label: string;
}

interface SetupWizardProps {
  cameraProfile: string;
  pitchLengthM?: string;
  automationAdmitted?: boolean;
  manualTaggingPermitted?: boolean;
  cannotMeasure?: string[];
  teamClusters?: TeamCluster[];
}

export default function SetupWizard({
  cameraProfile,
  pitchLengthM = '',
  automationAdmitted = false,
  manualTaggingPermitted = true,
  cannotMeasure = [],
  teamClusters = [],
}: SetupWizardProps) {
  return (
    <section aria-label="Setup wizard" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Setup wizard</h4>
      <label className="block text-xs text-slate-400">
        Periods
        <input defaultValue="1,2" className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
      </label>
      <label className="block text-xs text-slate-400">
        Pitch length (m)
        <input defaultValue={pitchLengthM} className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
      </label>
      <label className="block text-xs text-slate-400">
        Camera profile
        <input defaultValue={cameraProfile} readOnly className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
      </label>
      <p className="text-xs text-slate-400">Team mapping: colour clusters are suggestions, not semantic home/away labels.</p>
      {teamClusters.map((cluster) => (
        <p key={cluster.id} className="text-xs text-slate-300">{cluster.label}</p>
      ))}
      <p className="text-xs text-slate-400">Calibration: four-point compatibility retained; not a certification of whole-pitch coverage.</p>
      <label className="flex items-center gap-2 text-xs text-slate-400">
        <input type="checkbox" />
        Cloud permission
      </label>
      {manualTaggingPermitted && <p className="text-xs text-emerald-300">Manual tagging permitted.</p>}
      {!automationAdmitted && (
        <p className="text-xs text-amber-200">Rejected automation still permits tagging. Not a certification of the current implementation.</p>
      )}
      {cannotMeasure.length > 0 && (
        <p className="text-xs text-slate-500">Cannot measure: {cannotMeasure.join(', ')}</p>
      )}
    </section>
  );
}
