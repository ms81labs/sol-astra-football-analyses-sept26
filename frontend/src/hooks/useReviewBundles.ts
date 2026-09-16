import { useState, useEffect, useCallback } from 'react';
import type { ReviewBundle } from '../types';
import { fetchBundles, deleteBundle } from '../utils/api';

interface UseReviewBundlesOptions {
  autoLoad?: boolean;
  filterTags?: string[];
}

interface UseReviewBundlesReturn {
  bundles: ReviewBundle[];
  isLoading: boolean;
  error: string | null;
  loadBundles: (tags?: string[]) => Promise<void>;
  removeBundle: (bundleId: string) => Promise<void>;
  clearError: () => void;
}

export function useReviewBundles(options: UseReviewBundlesOptions = {}): UseReviewBundlesReturn {
  const { autoLoad = true, filterTags } = options;

  const [bundles, setBundles] = useState<ReviewBundle[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadBundles = useCallback(async (tags?: string[]) => {
    setIsLoading(true);
    setError(null);
    try {
      const loadedBundles = await fetchBundles(tags ?? filterTags);
      setBundles(loadedBundles);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load bundles';
      setError(message);
      console.error('loadBundles error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [filterTags]);

  const removeBundle = useCallback(async (bundleId: string): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      await deleteBundle(bundleId);
      setBundles((prev) => prev.filter((b) => b.id !== bundleId));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete bundle';
      setError(message);
      console.error('removeBundle error:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  useEffect(() => {
    if (autoLoad) {
      void loadBundles();
    }
  }, [autoLoad, loadBundles]);

  return {
    bundles,
    isLoading,
    error,
    loadBundles,
    removeBundle,
    clearError,
  };
}
