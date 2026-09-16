import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';

import SetupWizard from './SetupWizard';

afterEach(cleanup);

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

it('previews landmark fit without committing calibration or implying whole-pitch coverage', () => {
  render(
    <SetupWizard
      cameraProfile="stitched_panoramic_view"
      landmarkPreview={{ residualP95M: 4.2, accepted: false, committed: false }}
    />,
  );
  expect(screen.getByText(/preview landmark fit/i)).toBeTruthy();
  expect(screen.getByText(/not committed/i)).toBeTruthy();
  expect(screen.getByText(/does not rerun image-space detection/i)).toBeTruthy();
});

it('does not invent a residual when landmark fit is unmeasured', () => {
  render(
    <SetupWizard
      cameraProfile="stitched_panoramic_view"
      landmarkPreview={{ residualP95M: null, accepted: false, committed: false, measured: false }}
    />,
  );
  expect(screen.getByText(/landmark residual unmeasured/i)).toBeTruthy();
  expect(screen.queryByText(/p95 4\.2/i)).toBeNull();
  expect(screen.getByText(/does not rerun image-space detection/i)).toBeTruthy();
});
