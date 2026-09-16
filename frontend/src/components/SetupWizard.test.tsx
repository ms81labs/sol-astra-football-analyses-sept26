import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';

import SetupWizard from './SetupWizard';

it('collects periods, dimensions, camera, team mapping, calibration and rights without certifying automation', () => {
  render(
    <SetupWizard
      cameraProfile="handheld_low_angle"
      pitchLengthM=""
      automationAdmitted={false}
      manualTaggingPermitted
      cannotMeasure={['physical_metrics']}
      teamClusters={[{ id: 1, label: 'cluster 1' }]}
    />,
  );
  expect(screen.getByText(/setup wizard/i)).toBeTruthy();
  expect(screen.getByLabelText(/periods/i)).toBeTruthy();
  expect(screen.getByLabelText(/pitch length/i)).toBeTruthy();
  expect(screen.getByLabelText(/camera profile/i)).toBeTruthy();
  expect(screen.getByText(/suggestions, not semantic home\/away/i)).toBeTruthy();
  expect(screen.getByText(/calibration/i)).toBeTruthy();
  expect(screen.getByLabelText(/cloud permission/i)).toBeTruthy();
  expect(screen.getByText(/manual tagging permitted/i)).toBeTruthy();
  expect(screen.getAllByText(/not a certification/i).length).toBeGreaterThanOrEqual(1);
});
