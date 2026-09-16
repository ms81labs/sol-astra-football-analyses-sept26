interface ReleaseGateProps {
  publicExposureAllowed?: boolean;
}

export default function ReleaseGate({ publicExposureAllowed }: ReleaseGateProps) {
  return (
    <section aria-label="Release gate" className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs text-slate-300 space-y-1">
      <h3 className="text-[11px] uppercase tracking-wide text-slate-500">Release gate</h3>
      <p>No public exposure before the required security review.</p>
      <p>Protocol and network allowlist admits loopback and local files only.</p>
      <p>Constrained decoder arguments stay local; worker egress is deny-by-default.</p>
      <p>Least privilege storage credentials are object-scoped.</p>
      {publicExposureAllowed === false && <p>Public exposure remains blocked.</p>}
    </section>
  );
}
