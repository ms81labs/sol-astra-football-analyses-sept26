import ModalDialog from './ModalDialog';
import { useState, useCallback } from 'react';
import type { ReviewBundle, ReviewBundleItem } from '../types';
import { useReviewBundles } from '../hooks/useReviewBundles';
import type { PlaylistLoadResult } from './CoachInsights';

interface BundleListPanelProps {
  onLoadPlaylist: (items: ReviewBundleItem[]) => Promise<PlaylistLoadResult>;
  onClose: () => void;
}

export default function BundleListPanel({ onLoadPlaylist, onClose }: BundleListPanelProps) {
  const { bundles, isLoading, error, loadBundles, removeBundle } = useReviewBundles({ autoLoad: true });
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const handleLoadPlaylist = useCallback(
    async (bundle: ReviewBundle) => {
      setLoadingId(bundle.id);
      setLoadError(null);
      try {
        const result = await onLoadPlaylist(bundle.items);
        if (result.success) {
          onClose();
        } else {
          setLoadError(result.error ?? 'Could not load playlist.');
        }
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : 'Could not load playlist.');
      } finally {
        setLoadingId(null);
      }
    },
    [onLoadPlaylist, onClose],
  );

  const handleDelete = async (bundleId: string) => {
    setDeletingId(bundleId);
    try {
      await removeBundle(bundleId);
    } finally {
      setDeletingId(null);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    if (Number.isNaN(date.getTime())) return dateString;
    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <ModalDialog label="Saved Playlists" onClose={onClose}>
      <div className="bg-slate-800 border border-slate-700 rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <h3 className="text-base font-semibold text-emerald-400">Saved Playlists</h3>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-200 transition"
            aria-label="Close"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {loadError && (
            <div className="mb-3 rounded border border-rose-700/70 bg-rose-900/30 px-3 py-2 text-xs text-rose-300">
              {loadError}
            </div>
          )}
          {isLoading && bundles.length === 0 ? (
            <div className="text-center text-slate-500 py-8">
              <p className="text-sm">Loading playlists...</p>
            </div>
          ) : error ? (
            <div className="text-center text-rose-400 py-8">
              <p className="text-sm">{error}</p>
              <button
                onClick={() => void loadBundles()}
                className="mt-2 text-xs text-emerald-400 hover:underline"
              >
                Retry
              </button>
            </div>
          ) : bundles.length === 0 ? (
            <div className="text-center text-slate-500 py-8 border border-dashed border-slate-700 rounded-lg">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mx-auto mb-3 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
              <p className="text-sm">No saved playlists yet</p>
              <p className="text-xs text-slate-600 mt-1">Save annotations as playlists to review later</p>
            </div>
          ) : (
            <div className="space-y-3">
              {bundles.map((bundle) => (
                <div
                  key={bundle.id}
                  className="p-3 bg-slate-900 rounded-lg border border-slate-700 hover:border-slate-600 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-semibold text-slate-200 truncate">{bundle.name}</h4>
                      {bundle.description && (
                        <p className="text-xs text-slate-400 mt-1 line-clamp-2">{bundle.description}</p>
                      )}
                      <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
                        <span>{bundle.items.length} item{bundle.items.length !== 1 ? 's' : ''}</span>
                        <span>•</span>
                        <span>{formatDate(bundle.createdAt)}</span>
                      </div>
                      {bundle.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {bundle.tags.map((tag) => (
                            <span
                              key={tag}
                              className="px-2 py-0.5 bg-slate-700 rounded text-[10px] text-slate-400"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="flex flex-col gap-2 shrink-0">
                      <button
                        onClick={() => void handleLoadPlaylist(bundle)}
                        disabled={loadingId === bundle.id}
                        className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 rounded text-xs font-semibold transition text-white"
                      >
                        {loadingId === bundle.id ? 'Loading...' : 'Load'}
                      </button>
                      <button
                        onClick={() => void handleDelete(bundle.id)}
                        disabled={deletingId === bundle.id}
                        className="px-3 py-1.5 bg-slate-700 hover:bg-rose-600/50 disabled:opacity-50 rounded text-xs font-medium transition text-slate-400 hover:text-rose-300"
                      >
                        {deletingId === bundle.id ? '...' : 'Delete'}
                      </button>
                    </div>
                  </div>

                  {bundle.items.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-700">
                      <p className="text-[10px] text-slate-500 uppercase tracking-wide mb-2">Preview</p>
                      <div className="space-y-1 max-h-24 overflow-y-auto">
                        {bundle.items.slice(0, 3).map((item) => (
                          <div key={item.annotationId} className="text-xs text-slate-400 truncate flex items-center gap-2">
                            <span className="w-16 shrink-0 font-mono text-slate-600">F{item.frameStart}</span>
                            <span className="truncate">{item.label || 'Untitled annotation'}</span>
                          </div>
                        ))}
                        {bundle.items.length > 3 && (
                          <p className="text-xs text-slate-600">+{bundle.items.length - 3} more</p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="p-4 border-t border-slate-700 flex justify-between items-center">
          <button
            onClick={() => void loadBundles()}
            disabled={isLoading}
            className="text-xs text-slate-400 hover:text-slate-200 transition disabled:opacity-50"
          >
            Refresh
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-xs font-medium text-slate-300 transition"
          >
            Close
          </button>
        </div>
      </div>
    </ModalDialog>
  );
}
