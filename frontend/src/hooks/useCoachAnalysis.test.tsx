import { Suspense, startTransition, useLayoutEffect, useState } from 'react';
import { act, cleanup, render, renderHook, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { RuntimeCapabilities } from '../types';
import { useCoachAnalysis } from './useCoachAnalysis';

const localOnlyCapabilities: RuntimeCapabilities = {
  analysisProviders: ['local'],
  defaultAnalysisProvider: 'local',
  pdfExportAvailable: false,
};

const cloudCapabilities: RuntimeCapabilities = {
  analysisProviders: ['local', 'cloud'],
  defaultAnalysisProvider: 'local',
  pdfExportAvailable: false,
};

afterEach(cleanup);

it('starts on the first rendered coach tab', () => {
  const { result } = renderHook(() => useCoachAnalysis({
    runtimeCapabilities: localOnlyCapabilities,
    runMatchAnalysis: vi.fn(),
  }));

  expect(result.current.activeTab).toBe('analysis');
});

describe('useCoachAnalysis provider capabilities', () => {
  it('uses local when an unsupported cloud provider is declared as the default', () => {
    const { result } = renderHook(() => useCoachAnalysis({
      runtimeCapabilities: {
        ...localOnlyCapabilities,
        defaultAnalysisProvider: 'cloud',
      },
      runMatchAnalysis: vi.fn(),
    }));

    expect(result.current.llmProvider).toBe('local');
  });

  it('keeps an unsupported cloud selection local at the action boundary', async () => {
    const runMatchAnalysis = vi.fn().mockResolvedValue({ verdict: 'onside' });
    const { result } = renderHook(() => useCoachAnalysis({
      runtimeCapabilities: localOnlyCapabilities,
      runMatchAnalysis,
    }));

    act(() => result.current.selectLlmProvider('cloud'));
    expect(result.current.llmProvider).toBe('local');
    await act(() => result.current.runScenario({
      matchId: 'match-1',
      currentFrame: 12,
      scenario: 'offside',
    }));

    expect(runMatchAnalysis).toHaveBeenCalledWith('match-1', 'offside', 'local', 12);
  });

  it('runs locally immediately after cloud capability is removed', async () => {
    const runMatchAnalysis = vi.fn().mockResolvedValue({ verdict: 'onside' });
    const { result, rerender } = renderHook(
      ({ runtimeCapabilities }) => useCoachAnalysis({ runtimeCapabilities, runMatchAnalysis }),
      { initialProps: { runtimeCapabilities: cloudCapabilities } },
    );
    act(() => result.current.selectLlmProvider('cloud'));
    expect(result.current.llmProvider).toBe('cloud');
    const runScenario = result.current.runScenario;

    rerender({ runtimeCapabilities: localOnlyCapabilities });
    expect(result.current.llmProvider).toBe('local');
    await act(() => runScenario({
      matchId: 'match-1',
      currentFrame: 12,
      scenario: 'spacing',
    }));

    expect(runMatchAnalysis).toHaveBeenCalledWith('match-1', 'spacing', 'local', 12);
  });

  it('does not resurrect a removed cloud selection when support returns', () => {
    const { result, rerender } = renderHook(
      ({ runtimeCapabilities }) => useCoachAnalysis({
        runtimeCapabilities,
        runMatchAnalysis: vi.fn(),
      }),
      { initialProps: { runtimeCapabilities: cloudCapabilities } },
    );
    act(() => result.current.selectLlmProvider('cloud'));

    rerender({ runtimeCapabilities: localOnlyCapabilities });
    rerender({ runtimeCapabilities: cloudCapabilities });

    expect(result.current.llmProvider).toBe('local');
  });

  it('does not authorize cloud from a capability render that never commits', async () => {
    const runMatchAnalysis = vi.fn().mockResolvedValue({ verdict: 'onside' });
    const suspended = new Promise<never>(() => undefined);
    let suspend = false;
    let runScenario: ReturnType<typeof useCoachAnalysis>['runScenario'] | undefined;
    let setCapabilities: ((capabilities: RuntimeCapabilities) => void) | undefined;

    function Harness() {
      const [runtimeCapabilities, updateCapabilities] = useState<RuntimeCapabilities>({
        ...cloudCapabilities,
        defaultAnalysisProvider: 'cloud',
      });
      const coach = useCoachAnalysis({ runtimeCapabilities, runMatchAnalysis });
      useLayoutEffect(() => {
        setCapabilities = updateCapabilities;
        runScenario ??= coach.runScenario;
      }, [coach.runScenario]);
      if (suspend) throw suspended;
      return <span>{coach.llmProvider}</span>;
    }

    render(<Suspense fallback={<span>pending</span>}><Harness /></Suspense>);
    act(() => setCapabilities!(localOnlyCapabilities));
    expect(screen.getByText('local')).toBeTruthy();

    suspend = true;
    act(() => startTransition(() => setCapabilities!(cloudCapabilities)));
    expect(screen.getByText('local')).toBeTruthy();
    await act(() => runScenario!({
      matchId: 'match-1',
      currentFrame: 12,
      scenario: 'offside',
    }));

    expect(runMatchAnalysis).toHaveBeenCalledWith('match-1', 'offside', 'local', 12);
  });
});


it('invalidates pending frame analysis when the displayed frame advances', async () => {
  let finish!: (result: unknown) => void;
  const runMatchAnalysis = vi.fn(() => new Promise(resolve => { finish = resolve; }));
  const { result, rerender } = renderHook(({ currentFrame }) => useCoachAnalysis({ runtimeCapabilities: localOnlyCapabilities, runMatchAnalysis, currentFrame }), { initialProps: { currentFrame: 0 } });
  let request!: Promise<void>;
  act(() => { request = result.current.runScenario({ matchId: 'm', currentFrame: 0, scenario: 'offside' }); });
  rerender({ currentFrame: 1 });
  expect(result.current.llmThinking).toBe(false);
  await act(async () => { finish({ offside_x: 33 }); await request; });
  expect(result.current.llmResponse).toBeNull();
});

it('clearResponse invalidates a pending frame response immediately', async () => {
  let finish!: (result: unknown) => void;
  const { result } = renderHook(() => useCoachAnalysis({ runtimeCapabilities: localOnlyCapabilities, runMatchAnalysis: () => new Promise(resolve => { finish = resolve; }) }));
  let request!: Promise<void>;
  act(() => { request = result.current.runScenario({ matchId: 'm', currentFrame: 0, scenario: 'spacing' }); });
  act(() => result.current.clearResponse());
  expect(result.current.llmThinking).toBe(false);
  await act(async () => { finish({ offside_x: 33 }); await request; });
  expect(result.current.llmResponse).toBeNull();
});
