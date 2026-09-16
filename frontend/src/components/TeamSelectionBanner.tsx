import type { TeamCluster } from '../types';

interface TeamSelectionBannerProps {
  clusters: TeamCluster[];
  isSubmitting: boolean;
  onSelectCluster: (clusterId: number) => void;
}

function swatchStyle(rgbCentroid: number[]): string {
  const [red = 128, green = 128, blue = 128] = rgbCentroid;
  return `rgb(${Math.round(red)}, ${Math.round(green)}, ${Math.round(blue)})`;
}

function TeamSelectionBanner({ clusters, isSubmitting, onSelectCluster }: TeamSelectionBannerProps) {
  if (clusters.length === 0) {
    return null;
  }

  return (
    <section className="mb-6 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4">
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-amber-200">Detected Team Colors</h2>
        <p className="text-xs text-amber-100/80">
          Pick which detected cluster belongs to your team. The backend will relabel the stored match without rerunning video tracking.
        </p>
        <p className="mt-1 text-xs font-medium text-amber-200">
          Tactical interpretation is paused until a team cluster is chosen.
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {clusters.map((cluster) => (
          <button
            key={cluster.clusterId}
            type="button"
            disabled={isSubmitting}
            onClick={() => onSelectCluster(cluster.clusterId)}
            className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-left transition hover:border-amber-400 disabled:cursor-not-allowed disabled:opacity-60"
            aria-label={`Use cluster ${cluster.clusterId}`}
          >
            <div className="mb-2 flex items-center gap-3">
              <span
                className="h-6 w-6 rounded-full border border-white/20"
                style={{ backgroundColor: swatchStyle(cluster.rgbCentroid) }}
              />
              <div>
                <p className="text-sm font-semibold text-slate-100">Cluster {cluster.clusterId}</p>
                <p className="text-xs text-slate-400">{cluster.trackIds.length} tracked players</p>
              </div>
            </div>
            <p className="text-xs text-slate-500 font-mono">
              RGB {cluster.rgbCentroid.map((value) => Math.round(value)).join(', ')}
            </p>
          </button>
        ))}
      </div>
    </section>
  );
}

export default TeamSelectionBanner;
