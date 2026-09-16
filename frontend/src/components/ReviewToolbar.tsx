import { useRef, useState } from 'react';

import type { TacticalAnnotation } from '../types';

interface ReviewToolbarProps {
    onCreateNote: (text: string) => Promise<TacticalAnnotation | null>;
    onCreateTaggedMoment: (text: string) => Promise<TacticalAnnotation | null>;
}

export default function ReviewToolbar({ onCreateNote, onCreateTaggedMoment }: ReviewToolbarProps) {
    const inputRef = useRef<HTMLInputElement>(null);
    const [isSaving, setIsSaving] = useState(false);

    const submit = async (action: (value: string) => Promise<TacticalAnnotation | null>) => {
        if (isSaving) return;
        const trimmed = inputRef.current?.value.trim() || '';
        if (!trimmed) return;
        setIsSaving(true);
        try {
            const created = await action(trimmed);
            if (created && inputRef.current) {
                inputRef.current.value = '';
            }
        } catch {
            // The caller owns error reporting; keep the unsaved text here.
        } finally {
            setIsSaving(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            submit(onCreateNote);
        }
    };

    return (
        <div className="space-y-2">
            <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 p-3">
                <label className="sr-only" htmlFor="annotation-text">
                    Annotation text
                </label>
                <input
                    ref={inputRef}
                    id="annotation-text"
                    type="text"
                    placeholder="Type a note, press Enter to save..."
                    onKeyDown={handleKeyDown}
                    disabled={isSaving}
                    className="flex-1 min-w-0 rounded border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-500"
                />
                <button
                    type="button"
                    onClick={() => submit(onCreateNote)}
                    disabled={isSaving}
                    className="rounded border border-emerald-700 bg-emerald-900/50 px-3 py-2 text-sm text-emerald-300 hover:bg-emerald-900 transition-colors"
                >
                    Note
                </button>
                <button
                    type="button"
                    onClick={() => submit(onCreateTaggedMoment)}
                    disabled={isSaving}
                    className="rounded border border-amber-700 bg-amber-900/50 px-3 py-2 text-sm text-amber-300 hover:bg-amber-900 transition-colors"
                >
                    Tag
                </button>
            </div>
            <p className="text-[11px] text-slate-600">Press Enter for note, or use Tag for a reviewable moment.</p>
        </div>
    );
}
