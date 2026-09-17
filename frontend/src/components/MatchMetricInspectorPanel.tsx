import { useEffect, useState } from 'react';

import MetricInspector from './MetricInspector';
import { fetchMetricInspect, type MetricInspect } from '../utils/workbench';

interface MatchMetricInspectorPanelProps {
  matchId?: string;
}

export default function MatchMetricInspectorPanel({ matchId }: MatchMetricInspectorPanelProps) {
  const [inspect, setInspect] = useState<MetricInspect | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMetricInspect('my_team_distance_m', matchId)
      .then((payload) => {
        if (!cancelled) setInspect(payload);
      })
      .catch(() => {
        if (!cancelled) setInspect(null);
      });
    return () => {
      cancelled = true;
    };
  }, [matchId]);

  if (!inspect) return null;
  return (
    <MetricInspector
      metric={inspect.metric}
      unit={inspect.unit ?? 'metres'}
      denominator={inspect.denominator ?? 'identity_continuous_eligible_seconds'}
      definitionVersion={inspect.definitionVersion}
      eligibleDuration={inspect.eligibleDuration}
      exclusions={inspect.exclusions}
      value={inspect.publishedValue}
      availability={inspect.rendered === 'unavailable' ? 'unknown' : 'available'}
    />
  );
}
