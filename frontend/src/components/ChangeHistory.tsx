import { canUndo, commandState, type CommandReceipt } from '../utils/commandLifecycle';

interface ChangeHistoryProps {
  items: CommandReceipt[];
  onUndo?: (correctionId: string) => void;
}

export default function ChangeHistory({ items, onUndo }: ChangeHistoryProps) {
  return (
    <section aria-label="Change history" className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs text-slate-300 space-y-2">
      <h3 className="text-[11px] uppercase tracking-wide text-slate-500">Undoable change history</h3>
      <p className="text-slate-400">Original correction retained. Undo writes a new version and does not rewrite past outcomes.</p>
      {items.length === 0 ? (
        <p className="text-slate-500">No corrections yet.</p>
      ) : (
        <ul className="space-y-1">
          {items.map((item) => (
            <li key={item.correctionId} className="flex items-center justify-between gap-2">
              <span className="font-mono">
                <span>{item.correctionId}</span>
                {` · ${item.kind} · ${commandState(item)}`}
                {item.appliedGeneration ? ` · generation ${item.appliedGeneration}` : ''}
                {item.author ? ` · ${item.author}` : ''}
                {item.undoOf ? ` · undo of ${item.undoOf}` : ''}
              </span>
              {canUndo(item, items) && onUndo && (
                <button
                  type="button"
                  onClick={() => onUndo?.(item.correctionId)}
                  className="px-2 py-0.5 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700"
                >
                  Undo {item.correctionId}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
