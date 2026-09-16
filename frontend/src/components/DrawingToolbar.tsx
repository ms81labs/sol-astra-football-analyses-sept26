import { useRef } from 'react';
import type { DrawingMode } from './TacticalPitch';

interface DrawingToolbarProps {
    activeMode: DrawingMode;
    onArrow: () => void;
    onCircle: () => void;
    onCancel: () => void;
}

export default function DrawingToolbar({ activeMode, onArrow, onCircle, onCancel }: DrawingToolbarProps) {
    const arrowButtonRef = useRef<HTMLButtonElement>(null);

    return (
        <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-slate-400 font-medium">Draw:</span>
            <button
                ref={arrowButtonRef}
                type="button"
                onClick={onArrow}
                aria-pressed={activeMode === 'arrow'}
                className={`px-3 py-1.5 rounded border text-xs font-semibold transition-colors ${
                    activeMode === 'arrow'
                        ? 'bg-orange-600/20 border-orange-500 text-orange-400'
                        : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-500'
                }`}
            >
                Arrow
            </button>
            <button
                type="button"
                onClick={onCircle}
                aria-pressed={activeMode === 'circle'}
                className={`px-3 py-1.5 rounded border text-xs font-semibold transition-colors ${
                    activeMode === 'circle'
                        ? 'bg-cyan-600/20 border-cyan-500 text-cyan-400'
                        : 'bg-slate-900 border-slate-700 text-slate-400 hover:border-slate-500'
                }`}
            >
                Circle
            </button>
            {activeMode && (
                <button
                    type="button"
                    onClick={() => {
                        onCancel();
                        arrowButtonRef.current?.focus();
                    }}
                    className="px-3 py-1.5 rounded border border-slate-700 text-slate-400 text-xs hover:border-slate-500 hover:text-slate-300 transition-colors"
                >
                    Cancel
                </button>
            )}
            <span className="text-xs text-slate-600 italic">
                {activeMode === 'arrow' ? 'Click start point, then end point' : activeMode === 'circle' ? 'Click to place circle' : ''}
            </span>
        </div>
    );
}
