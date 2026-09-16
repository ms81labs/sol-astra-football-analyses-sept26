import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import BundleListPanel from './BundleListPanel';

const loadBundles = vi.fn();
const removeBundle = vi.fn();

vi.mock('../hooks/useReviewBundles', () => ({
  useReviewBundles: () => ({
    bundles: [
      {
        id: 'bundle-1',
        name: 'Same-match playlist',
        description: 'All on the current match',
        createdAt: 'not-a-date',
        tags: [],
        items: [
          {
            annotationId: 'item-1',
            matchId: 'match-1',
            frameStart: 10,
            frameEnd: 10,
            timestampStart: 2.0,
            timestampEnd: 2.0,
            label: 'Frame 10',
            description: 'Frame 10 - custom',
          },
        ],
      },
    ],
    isLoading: false,
    error: null,
    loadBundles,
    removeBundle,
  }),
}));

afterEach(() => {
  vi.clearAllMocks();
  cleanup();
});

describe('BundleListPanel', () => {
  it('preserves an invalid source date instead of showing Invalid Date', () => {
    render(<BundleListPanel onLoadPlaylist={vi.fn()} onClose={vi.fn()} />);

    expect(screen.getByText('not-a-date')).toBeTruthy();
  });

  it('waits for playlist load success before closing the modal', async () => {
    let resolveLoad: (value: { success: true }) => void = () => {};
    const onLoadPlaylist = vi.fn(
      () =>
        new Promise<{ success: true }>((resolve) => {
          resolveLoad = resolve;
        }),
    );
    const onClose = vi.fn();

    render(<BundleListPanel onLoadPlaylist={onLoadPlaylist} onClose={onClose} />);

    fireEvent.click(screen.getAllByRole('button', { name: /^load$/i })[0]);
    expect(onLoadPlaylist).toHaveBeenCalledOnce();
    expect(onClose).not.toHaveBeenCalled();

    resolveLoad({ success: true });

    await waitFor(() => {
      expect(onClose).toHaveBeenCalledOnce();
    });
  });

  it('shows an inline error when playlist loading is rejected', async () => {
    const onLoadPlaylist = vi.fn().mockResolvedValue({
      success: false,
      error: 'Playlist contains items from multiple matches. Load a single-match playlist.',
    });
    const onClose = vi.fn();

    render(<BundleListPanel onLoadPlaylist={onLoadPlaylist} onClose={onClose} />);

    fireEvent.click(screen.getAllByRole('button', { name: /^load$/i })[0]);

    expect(await screen.findByText(/multiple matches/i)).toBeTruthy();
    expect(onClose).not.toHaveBeenCalled();
  });
});
