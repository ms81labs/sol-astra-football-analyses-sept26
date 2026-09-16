interface RecoveryIncident {
  id: string;
  title: string;
}

interface RecoveryPanelProps {
  controllerRecorded?: boolean;
  unresolvedIncidents?: RecoveryIncident[];
  recoveryObjectivesDefined?: boolean;
  onRequestDeletion?: () => void;
}

export default function RecoveryPanel({
  controllerRecorded = false,
  unresolvedIncidents = [],
  recoveryObjectivesDefined = false,
  onRequestDeletion,
}: RecoveryPanelProps) {
  return (
    <section aria-label="Recovery and deletion" className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs text-slate-300 space-y-2">
      <h3 className="text-[11px] uppercase tracking-wide text-slate-500">Access/deletion</h3>
      <p>Track IDs do not anonymise identifiable video.</p>
      {!controllerRecorded && (
        <p className="text-amber-200">Controller and processor roles must be recorded before deletion can run.</p>
      )}
      <button
        type="button"
        onClick={onRequestDeletion}
        className="px-2 py-1 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700"
      >
        Request deletion
      </button>
      <div>
        <h4 className="text-[11px] uppercase tracking-wide text-slate-500">Operator-visible unresolved incidents</h4>
        {unresolvedIncidents.length === 0 ? (
          <p className="text-slate-500">No unresolved incidents recorded.</p>
        ) : (
          <ul className="space-y-1">
            {unresolvedIncidents.map((item) => (
              <li key={item.id}>{item.title}</li>
            ))}
          </ul>
        )}
      </div>
      {!recoveryObjectivesDefined && (
        <p className="text-amber-200">Recovery objectives remain unmeasured until data volume and analyst disruption are known.</p>
      )}
    </section>
  );
}
