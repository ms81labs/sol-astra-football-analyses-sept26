import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

import type {
  LlmResponse,
  RuntimeCapabilities,
} from '../types';

export interface TacticalReport {
  attacking: string;
  defensive: string;
  pressing: string;
  key_player: number;
  weaknesses: string;
  rating: number;
  summary: string;
  evidence?: string[];
  event_summary?: {
    eventCounts?: Record<string, number>;
    topPlayers?: Array<{
      trackId: number;
      team: string;
      involvements: number;
      actions?: Record<string, number>;
    }>;
  };
  player_focus?: {
    topCreator?: { trackId: number; team: string; label?: string; summary?: string };
    topFinisher?: { trackId: number; team: string; label?: string; summary?: string };
    topBallWinner?: { trackId: number; team: string; label?: string; summary?: string };
    otherKeyPlayers?: Array<{ trackId: number; team: string; label?: string; summary?: string }>;
  };
}

export interface DrillResponse {
  drills: Array<{
    name: string;
    objective: string;
    setup: string;
    duration: string;
  }>;
  focus_area: string;
  evidence?: string[];
  player_focus?: TacticalReport['player_focus'];
}

export type CoachAnalysisTab = 'analysis' | 'report' | 'drills';
export type CoachAnalysisScenario = 'offside' | 'spacing' | 'tactical_report' | 'drills';

interface UseCoachAnalysisOptions {
  currentFrame?: number;
  runtimeCapabilities: RuntimeCapabilities;
  runMatchAnalysis: (
    matchId: string,
    scenario: string,
    provider: 'local' | 'cloud',
    currentFrame: number,
  ) => Promise<unknown>;
}

interface RunScenarioInput {
  matchId: string | null;
  currentFrame: number;
  scenario: CoachAnalysisScenario;
}

export function useCoachAnalysis({
  runtimeCapabilities,
  runMatchAnalysis,
  currentFrame,
}: UseCoachAnalysisOptions) {
  const supportsCloudProvider = runtimeCapabilities.analysisProviders.includes('cloud');
  const defaultProvider: 'local' | 'cloud' = runtimeCapabilities.defaultAnalysisProvider === 'cloud' && supportsCloudProvider
    ? 'cloud'
    : 'local';
  const [llmThinking, setLlmThinking] = useState(false);
  const [llmResponse, setLlmResponse] = useState<LlmResponse>(null);
  const [selectedLlmProvider, setSelectedLlmProvider] = useState<'local' | 'cloud'>(defaultProvider);
  const [tacticalReport, setTacticalReport] = useState<TacticalReport | null>(null);
  const [drillResponse, setDrillResponse] = useState<DrillResponse | null>(null);
  const [activeTab, setActiveTab] = useState<CoachAnalysisTab>('analysis');
  const analysisRequestIdRef = useRef(0);
  const frameRequestRef = useRef(false);
  const supportsCloudProviderRef = useRef(supportsCloudProvider);

  useLayoutEffect(() => {
    supportsCloudProviderRef.current = supportsCloudProvider;
  }, [supportsCloudProvider]);

  const llmProvider: 'local' | 'cloud' = selectedLlmProvider === 'cloud' && supportsCloudProvider ? 'cloud' : 'local';

  useEffect(() => {
    setSelectedLlmProvider(defaultProvider);
  }, [defaultProvider, supportsCloudProvider]);

  const selectLlmProvider = useCallback((provider: 'local' | 'cloud') => {
    setSelectedLlmProvider(provider === 'cloud' && !supportsCloudProvider ? 'local' : provider);
  }, [supportsCloudProvider]);

  const resetAnalysis = useCallback(() => {
    analysisRequestIdRef.current += 1;
    setLlmThinking(false);
    setLlmResponse(null);
    setTacticalReport(null);
    setDrillResponse(null);
    setActiveTab('analysis');
  }, []);

  const clearResponse = useCallback(() => {
    if (frameRequestRef.current) {
      analysisRequestIdRef.current += 1;
      frameRequestRef.current = false;
      setLlmThinking(false);
    }
    setLlmResponse(null);
  }, []);

  useLayoutEffect(() => {
    clearResponse();
  }, [currentFrame, clearResponse]);

  const runScenario = useCallback(
    async ({ matchId, currentFrame, scenario }: RunScenarioInput) => {
      if (!matchId) return;
      const requestId = ++analysisRequestIdRef.current;
      frameRequestRef.current = scenario === 'offside' || scenario === 'spacing';
      setLlmResponse(null);
      if (scenario === 'tactical_report') {
        setTacticalReport(null);
        setDrillResponse(null);
      } else if (scenario === 'drills') {
        setDrillResponse(null);
        setTacticalReport(null);
      }
      setLlmThinking(true);

      try {
        const provider = llmProvider === 'cloud' && supportsCloudProviderRef.current ? 'cloud' : 'local';
        const result = await runMatchAnalysis(matchId, scenario, provider, currentFrame);
        if (analysisRequestIdRef.current !== requestId) return;
        if (scenario === 'tactical_report') {
          setTacticalReport(result as TacticalReport);
          setActiveTab('report');
        } else if (scenario === 'drills') {
          setDrillResponse(result as DrillResponse);
          setActiveTab('drills');
        } else {
          setLlmResponse(result as LlmResponse);
        }
      } catch (err) {
        if (analysisRequestIdRef.current !== requestId) return;
        setTacticalReport(null);
        setDrillResponse(null);
        setActiveTab('analysis');
        setLlmResponse({ error: err instanceof Error ? err.message : 'Failed to connect to LLM.' });
      } finally {
        if (analysisRequestIdRef.current === requestId) {
          setLlmThinking(false);
        }
      }
    },
    [llmProvider, runMatchAnalysis],
  );

  return {
    activeTab,
    clearResponse,
    drillResponse,
    llmProvider,
    llmResponse,
    llmThinking,
    resetAnalysis,
    runScenario,
    selectLlmProvider,
    setActiveTab,
    supportsCloudProvider,
    tacticalReport,
  };
}
