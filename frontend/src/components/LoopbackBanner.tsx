interface LoopbackBannerProps {
  deploymentBoundary?: string;
}

export default function LoopbackBanner({ deploymentBoundary = 'loopback' }: LoopbackBannerProps) {
  if (deploymentBoundary !== 'loopback') return null;
  return (
    <aside aria-label="Loopback deployment boundary" className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs text-slate-300 space-y-1">
      <p className="font-semibold text-amber-200">Loopback only</p>
      <p>Public and LAN access remain blocked until the separate network/security workstream is accepted.</p>
      <p className="text-slate-500">Origin/Host checks are not authentication. CORS is a browser boundary, not an access control.</p>
    </aside>
  );
}
