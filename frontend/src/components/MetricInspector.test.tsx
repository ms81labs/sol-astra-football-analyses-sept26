import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';

import MetricInspector from './MetricInspector';

it('shows unit, denominator, eligible duration and unknown as unavailable not zero', () => {
  render(
    <MetricInspector
      metric="my_team_distance_m"
      unit="metres"
      denominator="identity_continuous_eligible_seconds"
      definitionVersion="1"
      eligibleDuration={0}
      exclusions={['IDENTITY_DISCONTINUITY']}
      value={null}
      availability="unknown"
    />,
  );
  expect(screen.getByText(/metres/)).toBeTruthy();
  expect(screen.getByText(/identity_continuous_eligible_seconds/)).toBeTruthy();
  expect(screen.getByText(/definition v1/i)).toBeTruthy();
  expect(screen.getByText('Unavailable')).toBeTruthy();
  expect(screen.queryByText(/^0$/)).toBeNull();
});
