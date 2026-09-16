import type { FrameData } from '../types';
import ClockReadout from './ClockReadout';

interface EvidenceInspectorProps {
  frame: FrameData | null;
  cameraProfile?: string;
  reviewStatus?: 'unreviewed' | 'accepted' | 'rejected' | 'corrected';
  modelHash?: string;
  configVersion?: string;
  uncertainty?: string;
  detectorScore?: number | null;
  calibratedProbability?: number | null;
  confidenceInterval?: [number, number] | null;
}

function sourceLabel(frame: FrameData | null): string {
  if (!frame) return 'unknown';
  if (frame.Ball) return 'observed';
  if (frame.possession) return 'inferred or assigned';
  return 'unknown';
}

export default function EvidenceInspector({
  frame,
  cameraProfile,
  reviewStatus = 'unreviewed',
  modelHash,
  configVersion,
  uncertainty,
  detectorScore,
  calibratedProbability,
  confidenceInterval,
}: EvidenceInspectorProps) {
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
      {cameraProfile && <p>Camera profile: <span className="font-mono">{cameraProfile}</span></p>}
      {modelHash && <p>Model: <span className="font-mono">{modelHash}</span></p>}
      {configVersion && <p>Config: <span className="font-mono">{configVersion}</span></p>}
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
        presentationTimeSeconds={frame?.Timestamp ?? 0}
        matchClockSeconds={frame?.Timestamp ?? 0}
      />
      <p className="text-slate-500">Reviewed does not convert an inferred location into a directly observed one.</p>
    </section>
  );
}
