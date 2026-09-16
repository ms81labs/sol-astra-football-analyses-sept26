import type { TacticalAnnotation } from '../types';

interface AnnotationListProps {
    annotations: TacticalAnnotation[];
    onSeekToAnnotation: (annotation: TacticalAnnotation) => void;
    onDeleteAnnotation: (annotationId: string) => void;
}

function getAnnotationLabel(annotation: TacticalAnnotation, index: number): string {
    return annotation.text?.trim() || annotation.label?.trim() || `${annotation.type} ${index + 1}`;
}

export default function AnnotationList({ annotations, onSeekToAnnotation, onDeleteAnnotation }: AnnotationListProps) {
    if (annotations.length === 0) {
        return (
            <div className="rounded-lg border border-slate-700 bg-slate-900 p-4 text-center">
                <p className="text-sm text-slate-500 mb-1">No saved annotations yet.</p>
                <p className="text-xs text-slate-600">Use the toolbar below to add notes or tagged moments.</p>
            </div>
        );
    }

    const sortedAnnotations = [...annotations].sort((a, b) => a.frameStart - b.frameStart);

    return (
        <div className="space-y-2">
            <div className="text-xs text-slate-500 mb-2">{annotations.length} annotation{annotations.length !== 1 ? 's' : ''}, sorted by frame</div>
            {sortedAnnotations.map((annotation, index) => {
                const label = getAnnotationLabel(annotation, index);
                return (
                    <div
                        key={annotation.id}
                        className="flex items-center justify-between gap-3 rounded-lg border border-slate-700 bg-slate-900 p-3"
                    >
                        <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 mb-1">
                                <span className="rounded border border-slate-600 bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400 uppercase">
                                    {annotation.type}
                                </span>
                                <span className="text-xs text-slate-500 font-mono">
                                    {annotation.frameStart === annotation.frameEnd 
                                        ? `F${annotation.frameStart}` 
                                        : `F${annotation.frameStart}-${annotation.frameEnd}`}
                                </span>
                            </div>
                            <div className="truncate text-sm font-medium text-slate-100">{label}</div>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                            <button
                                type="button"
                                aria-label={`Seek to ${label}`}
                                onClick={() => onSeekToAnnotation(annotation)}
                                className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1.5 text-xs hover:bg-slate-700 transition-colors"
                            >
                                Seek
                            </button>
                            <button
                                type="button"
                                aria-label={`Delete ${label}`}
                                onClick={() => onDeleteAnnotation(annotation.id)}
                                className="rounded border border-rose-900/60 bg-rose-950/40 px-2.5 py-1.5 text-xs text-rose-300 hover:bg-rose-950/70 transition-colors"
                            >
                                Del
                            </button>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
