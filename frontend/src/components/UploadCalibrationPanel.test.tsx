import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { buildUploadConfig, createEmptyPointInputs } from '../utils/uploadConfig';
import UploadCalibrationPanel from './UploadCalibrationPanel';

afterEach(cleanup);

describe('UploadCalibrationPanel', () => {
  it('distinguishes a loaded manual-corner video from auto settings for the next upload', () => {
    render(
      <UploadCalibrationPanel
        autoHomography
        loadedVideoConfig={{
          autoHomography: false,
          manualHomographyPoints: [
            { x: 10, y: 10 }, { x: 1270, y: 10 },
            { x: 1270, y: 710 }, { x: 10, y: 710 },
          ],
        }}
        attackDirection="left_to_right"
        pointInputs={createEmptyPointInputs()}
        previewUrl={null}
        canRetryUpload={false}
        isRetryingUpload={false}
        uploadFailureGuidance={null}
        onAutoHomographyChange={() => {}}
        onAttackDirectionChange={() => {}}
        onPointChange={() => {}}
        onResetPoints={() => {}}
        onRetryUpload={() => {}}
      />,
    );

    expect(screen.getByText(/loaded video: manual corners supplied/i)).toBeTruthy();
    expect(screen.getByRole('checkbox', { name: 'Auto-detect pitch' })).toHaveProperty('checked', true);
  });

  it('does not guess a loaded video calibration mode when its config is unavailable', () => {
    render(
      <UploadCalibrationPanel
        autoHomography
        loadedVideoConfig={null}
        attackDirection="left_to_right"
        pointInputs={createEmptyPointInputs()}
        previewUrl={null}
        canRetryUpload={false}
        isRetryingUpload={false}
        uploadFailureGuidance={null}
        onAutoHomographyChange={() => {}}
        onAttackDirectionChange={() => {}}
        onPointChange={() => {}}
        onResetPoints={() => {}}
        onRetryUpload={() => {}}
      />,
    );

    expect(screen.getByText(/loaded video: calibration mode unavailable/i)).toBeTruthy();
  });

  it('offers a direct switch to manual calibration after an auto-homography miss', () => {
    const onAutoHomographyChange = vi.fn();

    render(
      <UploadCalibrationPanel
        autoHomography
        attackDirection="left_to_right"
        pointInputs={[
          { x: '', y: '' },
          { x: '', y: '' },
          { x: '', y: '' },
          { x: '', y: '' },
        ]}
        previewUrl={null}
        canRetryUpload={false}
        isRetryingUpload={false}
        uploadFailureGuidance='Turn off "Auto-detect pitch", enter the four pitch corners in the calibration strip above, then upload the video again.'
        onAutoHomographyChange={onAutoHomographyChange}
        onAttackDirectionChange={() => {}}
        onPointChange={() => {}}
        onResetPoints={() => {}}
        onRetryUpload={() => {}}
      />,
    );

    expect(screen.getByText(/auto-detect missed the pitch/i)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: /switch to manual calibration/i }));

    expect(onAutoHomographyChange).toHaveBeenCalledWith(false);
  });

  it('renders manual calibration inputs and lets the operator reset them', () => {
    const onPointChange = vi.fn();
    const onResetPoints = vi.fn();

    render(
      <UploadCalibrationPanel
        autoHomography={false}
        attackDirection="right_to_left"
        pointInputs={[
          { x: '10', y: '20' },
          { x: '110', y: '20' },
          { x: '110', y: '220' },
          { x: '10', y: '220' },
        ]}
        previewUrl="blob:test-video"
        canRetryUpload={false}
        isRetryingUpload={false}
        uploadFailureGuidance={null}
        onAutoHomographyChange={() => {}}
        onAttackDirectionChange={() => {}}
        onPointChange={onPointChange}
        onResetPoints={onResetPoints}
        onRetryUpload={() => {}}
      />,
    );

    expect(screen.getByText(/use the visible pitch corners in order/i)).toBeTruthy();

    fireEvent.change(screen.getByRole('spinbutton', { name: 'Top Left X' }), {
      target: { value: '12' },
    });
    fireEvent.click(screen.getByRole('button', { name: /reset points/i }));

    expect(onPointChange).toHaveBeenCalled();
    expect(onResetPoints).toHaveBeenCalledOnce();
  });

  it('exposes all four source-image corners as named keyboard inputs', () => {
    const onPointChange = vi.fn();
    const pointInputs = createEmptyPointInputs();
    const onRetryUpload = vi.fn(() =>
      buildUploadConfig({
        isVideo: true,
        llmProvider: 'local',
        attackDirection: 'left_to_right',
        pointInputs,
      }),
    );

    render(
      <UploadCalibrationPanel
        autoHomography={false}
        attackDirection="left_to_right"
        pointInputs={pointInputs}
        previewUrl="blob:test-video"
        canRetryUpload
        isRetryingUpload={false}
        uploadFailureGuidance={null}
        onAutoHomographyChange={() => {}}
        onAttackDirectionChange={() => {}}
        onPointChange={(index, axis, value) => {
          pointInputs[index][axis] = value;
          onPointChange(index, axis, value);
        }}
        onResetPoints={() => {}}
        onRetryUpload={onRetryUpload}
      />,
    );

    const coordinates = [
      ['Top Left X', '120'],
      ['Top Left Y', '80'],
      ['Top Right X', '1800'],
      ['Top Right Y', '90'],
      ['Bottom Right X', '1750'],
      ['Bottom Right Y', '990'],
      ['Bottom Left X', '150'],
      ['Bottom Left Y', '1010'],
    ] as const;
    const instructions = screen.getByText(/keyboard: enter source-frame x and y pixel coordinates/i);

    for (const [name, value] of coordinates) {
      const input = screen.getByRole('spinbutton', { name });
      expect(input.getAttribute('aria-describedby')).toBe(instructions.id);
      fireEvent.change(input, { target: { value } });
    }

    expect(onPointChange.mock.calls).toEqual([
      [0, 'x', '120'],
      [0, 'y', '80'],
      [1, 'x', '1800'],
      [1, 'y', '90'],
      [2, 'x', '1750'],
      [2, 'y', '990'],
      [3, 'x', '150'],
      [3, 'y', '1010'],
    ]);
    screen.getByRole('button', { name: /retry last video with current calibration/i }).click();

    expect(onRetryUpload).toHaveReturnedWith(
      expect.objectContaining({
        manualHomographyPoints: [
          { x: 120, y: 80 },
          { x: 1800, y: 90 },
          { x: 1750, y: 990 },
          { x: 150, y: 1010 },
        ],
      }),
    );
  });

  it('offers retrying the last video once manual calibration is ready', () => {
    const onRetryUpload = vi.fn();

    render(
      <UploadCalibrationPanel
        autoHomography={false}
        attackDirection="left_to_right"
        pointInputs={[
          { x: '10', y: '20' },
          { x: '110', y: '20' },
          { x: '110', y: '220' },
          { x: '10', y: '220' },
        ]}
        previewUrl="blob:test-video"
        canRetryUpload
        isRetryingUpload={false}
        uploadFailureGuidance="Turn off auto-detect and retry."
        onAutoHomographyChange={() => {}}
        onAttackDirectionChange={() => {}}
        onPointChange={() => {}}
        onResetPoints={() => {}}
        onRetryUpload={onRetryUpload}
      />,
    );

    const retryButton = screen
      .getAllByRole('button', { name: /retry last video with current calibration/i })
      .find((button) => !(button as HTMLButtonElement).disabled);

    expect(retryButton).toBeTruthy();
    fireEvent.click(retryButton as HTMLButtonElement);

    expect(onRetryUpload).toHaveBeenCalledOnce();
  });
});
