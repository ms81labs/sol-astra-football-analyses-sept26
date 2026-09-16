import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import CalibrationFramePicker from './CalibrationFramePicker';

afterEach(cleanup);

describe('CalibrationFramePicker', () => {
  it('captures the next empty manual point from a preview click', () => {
    const onPointChange = vi.fn();

    render(
      <CalibrationFramePicker
        previewUrl="blob:test-video"
        pointInputs={[
          { x: '', y: '' },
          { x: '', y: '' },
          { x: '', y: '' },
          { x: '', y: '' },
        ]}
        onPointChange={onPointChange}
      />,
    );

    const preview = screen.getByTestId('calibration-preview') as HTMLVideoElement;
    Object.defineProperty(preview, 'videoWidth', { configurable: true, value: 1920 });
    Object.defineProperty(preview, 'videoHeight', { configurable: true, value: 1080 });
    preview.getBoundingClientRect = () =>
      ({
        left: 10,
        top: 20,
        width: 200,
        height: 100,
        right: 210,
        bottom: 120,
        x: 10,
        y: 20,
        toJSON: () => ({}),
      }) as DOMRect;

    fireEvent.loadedMetadata(preview);
    fireEvent.click(preview, { clientX: 110, clientY: 70 });

    expect(onPointChange).toHaveBeenNthCalledWith(1, 0, 'x', '960');
    expect(onPointChange).toHaveBeenNthCalledWith(2, 0, 'y', '540');
  });

  it('shows which corner should be clicked next', () => {
    render(
      <CalibrationFramePicker
        previewUrl="blob:test-video"
        pointInputs={[
          { x: '10', y: '20' },
          { x: '', y: '' },
          { x: '', y: '' },
          { x: '', y: '' },
        ]}
        onPointChange={() => {}}
      />,
    );

    expect(screen.getByText(/click next: top right, or enter top right x and top right y above/i)).toBeTruthy();
  });
});
