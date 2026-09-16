import type { FrameData } from '../types';

interface EvidenceInspectorProps {
  frame: FrameData | null;
  cameraProfile?: string;
  reviewStatus?: 'unreviewed' | 'accepted' | 'rejected' | 'corrected';
}

function sourceLabel(frame: FrameData | null): string {
  if (!frame) return 'unknown';
  if (frame.Ball) return 'observed';
  if (frame.possession) return 'inferred or assigned';
  return 'unknown';
}

export default function EvidenceInspector({ frame, cameraProfile, reviewStatus = 'unreviewed' }: EvidenceInspectorProps) {
  return (
    <section aria-label="Evidence inspector" className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs text-slate-300 space-y-1">
      <h3 className="text-[11px] uppercase tracking-wide text-slate-500">Evidence inspector</h3>
      <p>Observation source: <span className="font-mono text-emerald-300">{sourceLabel(frame)}</span></p>
      <p>Review status: <span className="font-mono text-amber-300">{reviewStatus}</span></p>
      {cameraProfile && <p>Camera profile: <span className="font-mono">{cameraProfile}</span></p>}
      <p className="text-slate-500">Reviewed does not convert an inferred location into a directly observed one.</p>
    </section>
  );
}
