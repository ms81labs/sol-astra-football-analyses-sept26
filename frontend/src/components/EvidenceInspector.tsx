import { useEffect, useState } from 'react';

import type { FrameData } from '../types';
import { fetchMatchClock } from '../utils/workbench';
import ClockReadout from './ClockReadout';

interface EvidenceInspectorProps {
  matchId?: string;
  frame: FrameData | null;
  selectedInterval?: { start: number; end: number; evidenceIds: string[] } | null;
  cameraProfile?: string;
  reviewStatus?: 'unreviewed' | 'accepted' | 'rejected' | 'corrected';
  modelHash?: string;
  configVersion?: string;
  coordinateSpace?: string;
  definitionVersion?: string;
  uncertainty?: string;
  detectorScore?: number | null;
  calibratedProbability?: number | null;
  confidenceInterval?: [number, number] | null;
  proposal?: { modelId: string; modelVersion: string; evidenceIds: string[] } | null;
  onProposalDecision?: (decision: 'accept' | 'reject') => void;
}

function sourceLabel(frame: FrameData | null): string {
  if (!frame) return 'unknown';
  if (frame.Ball) return 'observed';
  if (frame.possession) return 'inferred or assigned';
  return 'unknown';
}

export default function EvidenceInspector({
  matchId,
  frame,
  selectedInterval,
  cameraProfile,
  reviewStatus = 'unreviewed',
  modelHash,
  configVersion,
  coordinateSpace,
  definitionVersion,
  uncertainty,
  detectorScore,
  calibratedProbability,
  confidenceInterval,
  proposal,
  onProposalDecision,
}: EvidenceInspectorProps) {
  const [matchClockOffsetSeconds, setMatchClockOffsetSeconds] = useState(0);
  const presentationTimeSeconds = frame?.Timestamp ?? 0;

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchClock(matchId)
      .then((payload) => {
        if (cancelled) return;
        if (typeof payload.presentationTimeSeconds === 'number' && typeof payload.matchClockSeconds === 'number') {
          setMatchClockOffsetSeconds(payload.matchClockSeconds - payload.presentationTimeSeconds);
        }
      })
      .catch(() => {
        if (!cancelled) setMatchClockOffsetSeconds(0);
      });
    return () => {
      cancelled = true;
    };
  }, [matchId]);

  return (
    <section aria-label="Evidence inspector" className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs text-slate-300 space-y-1">
      <h3 className="text-[11px] uppercase tracking-wide text-slate-500">Evidence inspector</h3>
      <p>
        <span aria-label="observation source icon">◎</span>
        {' '}Observation source: <span className="font-mono text-emerald-300">{sourceLabel(frame)}</span>
      </p>
      <p>
        <span aria-label="review status icon">✓</span>
        {' '}Review status: <span className="font-mono text-amber-300">{reviewStatus}</span>
      </p>
      {selectedInterval && <p>Selected source interval: {selectedInterval.start}s to {selectedInterval.end}s. Selected evidence: {selectedInterval.evidenceIds.join(', ') || 'unavailable'}.</p>}
      {proposal && <p>Model proposal: {proposal.modelId} · {proposal.modelVersion}</p>}
      {proposal && reviewStatus === 'unreviewed' && onProposalDecision && (
        <div className="flex gap-2">
          <button type="button" className="rounded bg-emerald-700 px-2 py-1 text-white" onClick={() => onProposalDecision('accept')}>Accept proposed event</button>
          <button type="button" className="rounded bg-slate-700 px-2 py-1 text-white" onClick={() => onProposalDecision('reject')}>Reject proposed event</button>
        </div>
      )}
      {cameraProfile && <p>Camera profile: <span className="font-mono">{cameraProfile}</span></p>}
      {modelHash && <p>Model: <span className="font-mono">{modelHash}</span></p>}
      {configVersion && <p>Config: <span className="font-mono">{configVersion}</span></p>}
      {coordinateSpace && <p>Coordinate space: <span className="font-mono">{coordinateSpace}</span></p>}
      {definitionVersion && <p>Definition version: <span className="font-mono">{definitionVersion}</span></p>}
      {uncertainty && <p>Uncertainty: <span className="font-mono">{uncertainty}</span></p>}
      {detectorScore != null && (
        <p>Detector score: <span className="font-mono">{detectorScore}</span></p>
      )}
      {calibratedProbability != null && (
        <p>Calibrated probability: <span className="font-mono">{calibratedProbability}</span></p>
      )}
      {confidenceInterval && (
        <p>
          Confidence interval:{' '}
          <span className="font-mono">[{confidenceInterval[0]}, {confidenceInterval[1]}]</span>
        </p>
      )}
      <ClockReadout
        presentationTimeSeconds={presentationTimeSeconds}
        matchClockSeconds={presentationTimeSeconds + matchClockOffsetSeconds}
      />
      <p className="text-slate-500">Reviewed does not convert an inferred location into a directly observed one.</p>
    </section>
  );
}
