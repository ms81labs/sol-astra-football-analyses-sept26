import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';

import ClockReadout from './ClockReadout';

it('keeps source presentation time separate from match clock and does not claim overlay alignment', () => {
  render(
    <ClockReadout presentationTimeSeconds={12.4} matchClockSeconds={57.4} />,
  );
  expect(screen.getByText(/source presentation time/i)).toBeTruthy();
  expect(screen.getByText('12.4s')).toBeTruthy();
  expect(screen.getByText(/match clock/i)).toBeTruthy();
  expect(screen.getByText('57.4s')).toBeTruthy();
  expect(screen.getByText(/does not make a timestamp overlay frame-accurate/i)).toBeTruthy();
});
