import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

import type {
  LlmResponse,
  RuntimeCapabilities,
} from '../types';

import type { TacticalReport, DrillResponse } from '../types';
import type { ReportView } from '../utils/reportLifecycle';
import { requireReportScope, reportNotice as explainReportError } from '../utils/reportLifecycle';
import { ApiError } from '../utils/request';
export type { TacticalReport, DrillResponse } from '../types';

export type CoachAnalysisTab = 'analysis' | 'report' | 'drills';
export type CoachAnalysisScenario = 'offside' | 'spacing' | 'tactical_report' | 'drills';

interface UseCoachAnalysisOptions {
  currentFrame?: number;
  activeMatchId?: string | null;
  generationId?: string | null;
  fetchReports?: (matchId: string, generationId: string, signal?: AbortSignal) => Promise<ReportView>;
  runtimeCapabilities: RuntimeCapabilities;
  runMatchAnalysis: (
    matchId: string,
    scenario: string,
    provider: 'local' | 'cloud',
    currentFrame: number,
    generationId?: string,
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
  activeMatchId, generationId, fetchReports,
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
  const scopeRef = useRef({ matchId: activeMatchId, generationId });
  const reportLoadIdRef = useRef(0);
  const [reportNotice, setReportNotice] = useState<string | null>(null);
  const [reportReload, setReportReload] = useState(0);
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
    setReportReload((value) => value + 1);
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

  useLayoutEffect(() => {
    scopeRef.current = { matchId: activeMatchId, generationId };
    analysisRequestIdRef.current += 1;
    reportLoadIdRef.current += 1;
    setTacticalReport(null);
    setDrillResponse(null);
    setLlmThinking(false);
    setReportNotice(generationId ? 'Report unavailable for this generation. Historical reports are retained.' : null);
  }, [activeMatchId, generationId]);

  useEffect(() => {
    if (!activeMatchId || !generationId || !fetchReports) return;
    const requestId = ++reportLoadIdRef.current;
    const controller = new AbortController();
    void fetchReports(activeMatchId, generationId, controller.signal).then((view) => {
      if (requestId !== reportLoadIdRef.current || controller.signal.aborted) return;
      if (view.matchId !== activeMatchId || view.generationId !== generationId) {
        throw new ApiError('Report snapshot changed.', 409, 'REPORT_GENERATION_MISMATCH');
      }
      // Validate all source-bound records before changing either report pane.
      const read = (task: 'tactical_report' | 'drills') => {
        const record = view.reports[task];
        if (!record) return null;
        if (record.matchId !== activeMatchId || record.generationId !== generationId) {
          throw new ApiError('Stored report snapshot changed.', 409, 'REPORT_GENERATION_MISMATCH');
        }
        return requireReportScope({ ...record.payload, status: record.status, reportId: record.reportId,
          validationDisposition: record.validationDisposition }, activeMatchId, generationId);
      };
      const tactical = read('tactical_report');
      const drills = read('drills');
      setTacticalReport(tactical);
      setDrillResponse(drills);
      setReportNotice(view.status === 'historical' ? 'Historical report — explicitly selected generation.'
        : !tactical && !drills ? 'Report unavailable for this generation. Older reports are retained as historical.'
        : view.notices.some((notice) => notice.code === 'REPORT_VERIFICATION_REQUIRED') ? 'A stored report requires verification.' : null);
    }).catch((error: unknown) => {
      if (requestId !== reportLoadIdRef.current || controller.signal.aborted) return;
      setTacticalReport(null); setDrillResponse(null);
      setReportNotice(explainReportError(error));
    });
    return () => controller.abort();
  }, [activeMatchId, generationId, fetchReports, reportReload]);

  const runScenario = useCallback(
    async ({ matchId, currentFrame, scenario }: RunScenarioInput) => {
      if (!matchId) return;
      const requestId = ++analysisRequestIdRef.current;
      const scope = scopeRef.current;
      reportLoadIdRef.current += 1;
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
        const isReport = scenario === 'tactical_report' || scenario === 'drills';
        if (isReport && (!scope.generationId || scope.matchId !== matchId)) {
          throw new ApiError('Select a committed match generation before requesting a report.', 409, 'GENERATION_REQUIRED');
        }
        const raw = isReport
          ? await runMatchAnalysis(matchId, scenario, provider, currentFrame, scope.generationId!)
          : await runMatchAnalysis(matchId, scenario, provider, currentFrame);
        const result = isReport ? requireReportScope(raw, matchId, scope.generationId!) : raw;
        if (analysisRequestIdRef.current !== requestId) return;
        if (scenario === 'tactical_report') {
          setReportNotice(null);
          setTacticalReport(result as TacticalReport);
          setActiveTab('report');
        } else if (scenario === 'drills') {
          setReportNotice(null);
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
        setReportNotice(explainReportError(err));
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
    reportNotice,
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
