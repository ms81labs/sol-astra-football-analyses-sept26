import { findNearestFrameIndex } from '../../utils/videoSync';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { FrameData, MatchIssue, ReviewRange, TacticalAnnotation } from '../../types';
import {
  createMatchAnnotation,
  createMatchIssue,
  deleteMatchAnnotation,
  deleteMatchIssue,
  fetchMatchAnnotations,
  fetchMatchIssues,
} from '../../utils/api';

type ReviewMode = 'arrow' | 'circle' | null;
type PitchAnnotationPlacementMode = 'circle' | 'arrow-start' | 'arrow-end' | null;

interface UseReviewSurfaceOptions {
  activeMatchId: string | null;
  activeGenerationId?: string | null;
  currentFrame: number;
  matchData: FrameData[];
  pausePlayback: () => void;
  clearResponse: () => void;
  onSeekFrame: (frame: number) => void;
  setLoadError: (message: string | null) => void;
}

export function useReviewSurface({
  activeMatchId,
  activeGenerationId,
  currentFrame,
  matchData,
  pausePlayback,
  clearResponse,
  onSeekFrame,
  setLoadError,
}: UseReviewSurfaceOptions) {
  const [annotationState, setAnnotationState] = useState<{
    matchId: string | null;
    items: TacticalAnnotation[];
  }>({ matchId: activeMatchId, items: [] });
  const [issueState, setIssueState] = useState<{
    matchId: string | null;
    items: MatchIssue[];
  }>({ matchId: activeMatchId, items: [] });
  const [reviewRange, setReviewRange] = useState<ReviewRange | null>(null);
  const [reviewMode, setReviewMode] = useState<ReviewMode>(null);
  const [pendingArrowStart, setPendingArrowStart] = useState<{ x: number; y: number } | null>(null);
  const reviewScope = `${activeMatchId ?? ''}:${activeGenerationId ?? ''}`;
  const [reviewScopeId, setReviewScopeId] = useState(reviewScope);

  const activeMatchIdRef = useRef<string | null>(activeMatchId);
  const setLoadErrorRef = useRef(setLoadError);

  if (reviewScopeId !== reviewScope) {
    setReviewScopeId(reviewScope);
    setReviewRange(null);
    setReviewMode(null);
    setPendingArrowStart(null);
  }

  useEffect(() => {
    activeMatchIdRef.current = activeMatchId;
  }, [activeMatchId]);

  useEffect(() => {
    setLoadErrorRef.current = setLoadError;
  }, [setLoadError]);

  const annotations = useMemo(() => {
    if (!activeMatchId) return [];
    return annotationState.matchId === activeMatchId ? annotationState.items : [];
  }, [activeMatchId, annotationState]);

  const issues = useMemo(() => {
    if (!activeMatchId) return [];
    return issueState.matchId === activeMatchId ? issueState.items : [];
  }, [activeMatchId, issueState]);

  useEffect(() => {
    if (!activeMatchId) {
      return;
    }

    let cancelled = false;
    const requestMatchId = activeMatchId;

    async function loadAnnotations() {
      try {
        const nextAnnotations = await fetchMatchAnnotations(requestMatchId);
        if (!cancelled && activeMatchIdRef.current === requestMatchId) {
          setAnnotationState({ matchId: requestMatchId, items: nextAnnotations });
        }
      } catch (err) {
        console.error('Could not load annotations for the active match.', err);
        if (!cancelled && activeMatchIdRef.current === requestMatchId) {
          setLoadErrorRef.current(err instanceof Error ? err.message : 'Failed to load annotations.');
          setAnnotationState({ matchId: requestMatchId, items: [] });
        }
      }
    }

    void loadAnnotations();

    return () => {
      cancelled = true;
    };
  }, [activeMatchId]);

  useEffect(() => {
    if (!activeMatchId) {
      return;
    }

    let cancelled = false;
    const requestMatchId = activeMatchId;

    async function loadIssues() {
      try {
        const nextIssues = await fetchMatchIssues(requestMatchId);
        if (!cancelled && activeMatchIdRef.current === requestMatchId) {
          setIssueState({ matchId: requestMatchId, items: nextIssues });
        }
      } catch (err) {
        console.error('Could not load issues for the active match.', err);
        if (!cancelled && activeMatchIdRef.current === requestMatchId) {
          setLoadErrorRef.current(err instanceof Error ? err.message : 'Failed to load match issues.');
          setIssueState({ matchId: requestMatchId, items: [] });
        }
      }
    }

    void loadIssues();

    return () => {
      cancelled = true;
    };
  }, [activeMatchId]);

  const pitchAnnotationPlacementMode: PitchAnnotationPlacementMode = useMemo(() => {
    if (reviewMode === 'circle') return 'circle';
    if (reviewMode === 'arrow') return pendingArrowStart ? 'arrow-end' : 'arrow-start';
    return null;
  }, [pendingArrowStart, reviewMode]);

  const buildReviewTiming = useCallback(() => {
    if (matchData.length === 0) return null;

    const range = reviewRange ?? { startFrame: currentFrame, endFrame: currentFrame };
    const maxFrame = matchData.length - 1;
    const clampFrame = (frame: number) => Math.min(maxFrame, Math.max(0, Number.isFinite(frame) ? Math.trunc(frame) : 0));
    const normalizedStart = clampFrame(range.startFrame);
    const normalizedEnd = clampFrame(range.endFrame);
    const frameStart = Math.min(normalizedStart, normalizedEnd);
    const frameEnd = Math.max(normalizedStart, normalizedEnd);

    return {
      frameStart,
      frameEnd,
      timestampStart: matchData[frameStart].Timestamp,
      timestampEnd: matchData[frameEnd].Timestamp,
    };
  }, [currentFrame, matchData, reviewRange]);

  const persistAnnotation = useCallback(
    async (payload: Omit<TacticalAnnotation, 'id' | 'matchId' | 'createdAt' | 'updatedAt'>) => {
      if (!activeMatchId) return null;
      const requestMatchId = activeMatchId;

      try {
        const created = await createMatchAnnotation(requestMatchId, payload);
        if (activeMatchIdRef.current === requestMatchId) {
          setLoadError(null);
          setAnnotationState((prev) => ({
            matchId: requestMatchId,
            items: [...(prev.matchId === requestMatchId ? prev.items : []), created],
          }));
        }
        return created;
      } catch (err) {
        console.error('Could not save annotation.', err);
        if (activeMatchIdRef.current === requestMatchId) {
          setLoadError(err instanceof Error ? err.message : 'Failed to save annotation.');
        }
        return null;
      }
    },
    [activeMatchId, setLoadError],
  );

  const persistIssue = useCallback(
    async (payload: Omit<MatchIssue, 'id' | 'matchId' | 'createdAt' | 'updatedAt'>) => {
      if (!activeMatchId) return null;
      const requestMatchId = activeMatchId;

      try {
        const created = await createMatchIssue(requestMatchId, payload);
        if (activeMatchIdRef.current === requestMatchId) {
          setLoadError(null);
          setIssueState((prev) => ({
            matchId: requestMatchId,
            items: [...(prev.matchId === requestMatchId ? prev.items : []), created],
          }));
        }
        return created;
      } catch (err) {
        console.error('Could not save match issue.', err);
        if (activeMatchIdRef.current === requestMatchId) {
          setLoadError(err instanceof Error ? err.message : 'Failed to save match issue.');
        }
        return null;
      }
    },
    [activeMatchId, setLoadError],
  );

  const handleCreateNote = useCallback(
    async (text: string) => {
      const timing = buildReviewTiming();
      if (!timing) return null;
      return persistAnnotation({
        type: 'note',
        ...timing,
        text,
      });
    },
    [buildReviewTiming, persistAnnotation],
  );

  const handleCreateTaggedMoment = useCallback(
    async (text: string) => {
      const timing = buildReviewTiming();
      if (!timing) return null;
      return persistAnnotation({
        type: 'moment',
        ...timing,
        label: text,
      });
    },
    [buildReviewTiming, persistAnnotation],
  );

  const handleCreateIssue = useCallback(
    async (payload: Pick<MatchIssue, 'bucket' | 'processingBackend' | 'evidenceTarget' | 'note'>) => {
      const timing = buildReviewTiming();
      if (!timing) return null;
      return persistIssue({
        ...timing,
        ...payload,
      });
    },
    [buildReviewTiming, persistIssue],
  );

  const handlePitchPointSelect = useCallback(
    async (point: { x: number; y: number }) => {
      if (reviewMode === 'circle') {
        const requestMatchId = activeMatchId;
        const timing = buildReviewTiming();
        if (!requestMatchId || !timing) return;
        const created = await persistAnnotation({
          type: 'circle',
          ...timing,
          x: point.x,
          y: point.y,
        });
        if (created && activeMatchIdRef.current === requestMatchId) {
          setReviewMode(null);
          setPendingArrowStart(null);
        }
        return;
      }

      if (reviewMode !== 'arrow') return;

      if (!pendingArrowStart) {
        setPendingArrowStart(point);
        return;
      }

      const requestMatchId = activeMatchId;
      const timing = buildReviewTiming();
      if (!requestMatchId || !timing) return;
      const created = await persistAnnotation({
        type: 'arrow',
        ...timing,
        x: pendingArrowStart.x,
        y: pendingArrowStart.y,
        x2: point.x,
        y2: point.y,
      });
      if (created && activeMatchIdRef.current === requestMatchId) {
        setReviewMode(null);
        setPendingArrowStart(null);
      }
    },
    [activeMatchId, buildReviewTiming, pendingArrowStart, persistAnnotation, reviewMode],
  );

  const handleSeekToAnnotation = useCallback(
    (annotation: TacticalAnnotation) => {
      const timestamps = matchData.map(frame => frame.Timestamp);
      const startFrame = findNearestFrameIndex(timestamps, annotation.timestampStart);
      const endFrame = findNearestFrameIndex(timestamps, annotation.timestampEnd);
      onSeekFrame(startFrame);
      setReviewRange({ startFrame, endFrame });
      pausePlayback();
      clearResponse();
    },
    [clearResponse, matchData, onSeekFrame, pausePlayback],
  );

  const handleDeleteAnnotation = useCallback(
    async (annotationId: string) => {
      if (!activeMatchId) return;
      const requestMatchId = activeMatchId;

      try {
        await deleteMatchAnnotation(requestMatchId, annotationId);
        if (activeMatchIdRef.current === requestMatchId) {
          setAnnotationState((prev) => ({
            matchId: requestMatchId,
            items: (prev.matchId === requestMatchId ? prev.items : []).filter(
              (annotation) => annotation.id !== annotationId,
            ),
          }));
        }
      } catch (err) {
        console.error('Could not delete annotation.', err);
        if (activeMatchIdRef.current === requestMatchId) {
          setLoadError(err instanceof Error ? err.message : 'Failed to delete annotation.');
        }
      }
    },
    [activeMatchId, setLoadError],
  );

  const handleSeekToIssue = useCallback(
    (issue: MatchIssue) => {
      const timestamps = matchData.map(frame => frame.Timestamp);
      const startFrame = findNearestFrameIndex(timestamps, issue.timestampStart);
      const endFrame = findNearestFrameIndex(timestamps, issue.timestampEnd);
      onSeekFrame(startFrame);
      setReviewRange({ startFrame, endFrame });
      pausePlayback();
      clearResponse();
    },
    [clearResponse, matchData, onSeekFrame, pausePlayback],
  );

  const handleDeleteIssue = useCallback(
    async (issueId: string) => {
      if (!activeMatchId) return;
      const requestMatchId = activeMatchId;

      try {
        await deleteMatchIssue(requestMatchId, issueId);
        if (activeMatchIdRef.current === requestMatchId) {
          setIssueState((prev) => ({
            matchId: requestMatchId,
            items: (prev.matchId === requestMatchId ? prev.items : []).filter((issue) => issue.id !== issueId),
          }));
        }
      } catch (err) {
        console.error('Could not delete match issue.', err);
        if (activeMatchIdRef.current === requestMatchId) {
          setLoadError(err instanceof Error ? err.message : 'Failed to delete match issue.');
        }
      }
    },
    [activeMatchId, setLoadError],
  );

  const startCirclePlacement = useCallback(() => {
    setReviewMode('circle');
    setPendingArrowStart(null);
  }, []);

  const startArrowPlacement = useCallback(() => {
    setReviewMode('arrow');
    setPendingArrowStart(null);
  }, []);

  const cancelPlacement = useCallback(() => {
    setReviewMode(null);
    setPendingArrowStart(null);
  }, []);

  return {
    annotations,
    issues,
    reviewRange,
    reviewMode,
    pitchAnnotationPlacementMode,
    setReviewRange,
    handleCreateNote,
    handleCreateTaggedMoment,
    handlePitchPointSelect,
    handleSeekToAnnotation,
    handleDeleteAnnotation,
    handleCreateIssue,
    handleSeekToIssue,
    handleDeleteIssue,
    startCirclePlacement,
    startArrowPlacement,
    cancelPlacement,
  };
}
