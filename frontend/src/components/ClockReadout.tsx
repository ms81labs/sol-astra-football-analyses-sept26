interface ClockReadoutProps {
  presentationTimeSeconds: number;
  matchClockSeconds: number;
}

export default function ClockReadout({
  presentationTimeSeconds,
  matchClockSeconds,
}: ClockReadoutProps) {
  return (
    <section aria-label="Clock mapping" className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs text-slate-300 space-y-1">
      <p>Source presentation time: <span className="font-mono text-emerald-300">{presentationTimeSeconds}s</span></p>
      <p>Match clock: <span className="font-mono">{matchClockSeconds}s</span></p>
      <p className="text-slate-500">An explicit mapping does not make a timestamp overlay frame-accurate.</p>
    </section>
  );
}
