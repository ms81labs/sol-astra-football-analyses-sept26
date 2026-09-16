import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import { useReviewBundles } from './useReviewBundles';

const { deleteBundle, fetchBundles } = vi.hoisted(() => ({
  deleteBundle: vi.fn(),
  fetchBundles: vi.fn(),
}));

vi.mock('../utils/api', () => ({ deleteBundle, fetchBundles }));

afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

it('reports a rejected delete without rejecting the caller', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => undefined);
  deleteBundle.mockRejectedValue(new Error('Delete failed'));
  const { result } = renderHook(() => useReviewBundles({ autoLoad: false }));

  await act(async () => {
    await result.current.removeBundle('bundle-1');
  });

  expect(result.current.error).toBe('Delete failed');
});
