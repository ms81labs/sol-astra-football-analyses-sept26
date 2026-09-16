import ModalDialog from './ModalDialog';
import { useState } from 'react';
import { createBundle } from '../utils/api';
import type { ReviewBundleItem, CreateBundleInput } from '../types';

interface SaveBundleButtonProps {
  currentFrame: number;
  events: ReviewBundleItem[];
  onSave?: (bundleId: string) => void;
}

interface SaveDialogState {
  isOpen: boolean;
  name: string;
  description: string;
  tags: string;
}

const DEFAULT_DIALOG: SaveDialogState = {
  isOpen: false,
  name: '',
  description: '',
  tags: '',
};

export default function SaveBundleButton({ currentFrame, events, onSave }: SaveBundleButtonProps) {
  const [dialog, setDialog] = useState<SaveDialogState>(DEFAULT_DIALOG);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const openDialog = () => {
    setDialog({
      isOpen: true,
      name: `Playlist ${new Date().toLocaleDateString()}`,
      description: `Review from frame ${currentFrame}`,
      tags: 'coach,tactical',
    });
    setError(null);
  };

  const closeDialog = () => {
    setDialog(DEFAULT_DIALOG);
    setError(null);
  };

  const handleSave = async () => {
    if (!dialog.name.trim()) {
      setError('Name is required');
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      const input: CreateBundleInput = {
        name: dialog.name.trim(),
        description: dialog.description.trim() || undefined,
        tags: dialog.tags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
        items: events.length > 0 ? events : undefined,
      };

      const bundle = await createBundle(input);
      onSave?.(bundle.id);
      closeDialog();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save playlist';
      setError(message);
      console.error('SaveBundle error:', err);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <>
      <button
        onClick={openDialog}
        className="w-full py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-xs font-semibold transition text-white flex items-center justify-center gap-2"
        disabled={isSaving}
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path d="M5 4a2 2 0 012-2h6a2 2 0 012 2v14l-5-2.5L5 18V4z" />
        </svg>
        Save Playlist
      </button>

      {dialog.isOpen && (
        <ModalDialog label="Save Review Playlist" onClose={closeDialog}>
          <div className="bg-slate-800 border border-slate-700 rounded-xl shadow-2xl w-full max-w-md mx-4 p-5">
            <h3 className="text-base font-semibold text-emerald-400 mb-4">Save Review Playlist</h3>

            <div className="space-y-4">
              <div>
                <label htmlFor="bundle-name" className="block text-xs font-medium text-slate-400 mb-1">
                  Name <span className="text-rose-400">*</span>
                </label>
                <input
                  id="bundle-name"
                  type="text"
                  value={dialog.name}
                  onChange={(e) => setDialog((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="My Review Playlist"
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  data-initial-focus
                />
              </div>

              <div>
                <label htmlFor="bundle-description" className="block text-xs font-medium text-slate-400 mb-1">
                  Description
                </label>
                <textarea
                  id="bundle-description"
                  value={dialog.description}
                  onChange={(e) => setDialog((prev) => ({ ...prev, description: e.target.value }))}
                  placeholder="Optional notes about this playlist..."
                  rows={2}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
                />
              </div>

              <div>
                <label htmlFor="bundle-tags" className="block text-xs font-medium text-slate-400 mb-1">
                  Tags <span className="text-slate-500">(comma-separated)</span>
                </label>
                <input
                  id="bundle-tags"
                  type="text"
                  value={dialog.tags}
                  onChange={(e) => setDialog((prev) => ({ ...prev, tags: e.target.value }))}
                  placeholder="coach, tactics, attacking"
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              {events.length > 0 && (
                <div className="p-3 bg-slate-900 rounded border border-slate-700">
                  <p className="text-xs text-slate-400 mb-2">
                    <span className="font-semibold text-slate-300">{events.length}</span> annotated item(s) will be saved:
                  </p>
                  <div className="max-h-24 overflow-y-auto space-y-1">
                    {events.slice(0, 5).map((item) => (
                      <div key={item.annotationId} className="text-xs text-slate-400 truncate">
                        {item.label || 'Untitled'} • Frame {item.frameStart}
                      </div>
                    ))}
                    {events.length > 5 && (
                      <p className="text-xs text-slate-500">...and {events.length - 5} more</p>
                    )}
                  </div>
                </div>
              )}

              {error && (
                <div className="p-2 bg-rose-900/20 border border-rose-700 rounded text-xs text-rose-400">
                  {error}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={closeDialog}
                disabled={isSaving}
                className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving || !dialog.name.trim()}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded text-xs font-semibold transition text-white"
              >
                {isSaving ? 'Saving...' : 'Save Playlist'}
              </button>
            </div>
          </div>
        </ModalDialog>
      )}
    </>
  );
}
