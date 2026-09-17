import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

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

  expect(screen.getByText(/does not rerun image-space detection/i)).toBeTruthy();
});

it('persists periods, pitch, camera, teams and rights through onSave', async () => {
  const onSave = vi.fn().mockResolvedValue(undefined);
  render(
    <SetupWizard
      matchId="match-a"
      cameraProfile="handheld_low_angle"
      pitchLengthM=""
      onSave={onSave}
    />,
  );
  fireEvent.change(screen.getByLabelText(/periods/i), { target: { value: '1,2,ET' } });
  fireEvent.change(screen.getByLabelText(/pitch length/i), { target: { value: '105' } });
  fireEvent.change(screen.getByLabelText(/camera profile/i), { target: { value: 'stable_elevated_wide' } });
  fireEvent.change(screen.getByLabelText(/home team/i), { target: { value: 'Home FC' } });
  fireEvent.change(screen.getByLabelText(/away team/i), { target: { value: 'Away FC' } });
  fireEvent.click(screen.getByLabelText(/cloud permission/i));
  fireEvent.click(screen.getByRole('button', { name: /save setup/i }));
  await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
  expect(onSave.mock.calls[0][0]).toEqual(expect.objectContaining({
    cameraProfile: 'stable_elevated_wide',
    pitchLengthM: 105,
    homeTeam: 'Home FC',
    awayTeam: 'Away FC',
    rights: expect.objectContaining({ cloudPermission: true }),
  }));
  expect(onSave.mock.calls[0][0].periods.map((period: { name: string }) => period.name)).toEqual(['1', '2', 'ET']);
});
