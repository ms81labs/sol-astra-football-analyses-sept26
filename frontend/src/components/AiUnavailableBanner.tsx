interface AiUnavailableBannerProps {
  providersEnabled?: boolean;
}

export default function AiUnavailableBanner({ providersEnabled = false }: AiUnavailableBannerProps) {
  if (providersEnabled) return null;
  return (
    <aside aria-label="AI unavailable" className="rounded-lg border border-amber-700/50 bg-amber-950/30 p-3 text-xs text-amber-100 space-y-1">
      <p className="font-semibold">AI unavailable</p>
      <p>Review, metrics and template reports remain available. The optional assistant is not required.</p>
    </aside>
  );
}
