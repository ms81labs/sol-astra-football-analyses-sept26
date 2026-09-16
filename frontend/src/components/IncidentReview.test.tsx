import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';

import IncidentReview from './IncidentReview';

afterEach(cleanup);

it('lets the reviewer choose a touch interval and stays indeterminate without an offside ruling', () => {
  render(
    <IncidentReview
      touchStart={12.04}
      touchEnd={12.16}
      samples={[
        { time: 12.04, attackerX: 9.7, offsideLineX: 10, indeterminate: true },
        { time: 12.16, attackerX: 10.3, offsideLineX: 10, indeterminate: true },
      ]}
    />,
  );
  expect(screen.getByLabelText(/touch interval start/i)).toBeTruthy();
  expect(screen.getByLabelText(/touch interval end/i)).toBeTruthy();
  expect(screen.getByText(/indeterminate/i)).toBeTruthy();
  expect(screen.queryByText(/offside ruling/i)).toBeNull();
  expect(screen.getByText(/not a validated measurement/i)).toBeTruthy();
  expect(screen.getByText(/video-language model confidence is not referee ground truth/i)).toBeTruthy();
  expect(screen.getByText(/broadcast replays from different times are not simultaneous evidence/i)).toBeTruthy();
  expect(screen.getByText(/elevated body parts through a ground-plane homography are not a precise offside line/i)).toBeTruthy();
  expect(screen.getByText(/an invisible player or ball cannot be repaired by a larger model/i)).toBeTruthy();
  fireEvent.change(screen.getByLabelText(/touch interval end/i), { target: { value: '12.20' } });
  expect((screen.getByLabelText(/touch interval end/i) as HTMLInputElement).value).toBe('12.20');
});

it('does not invent origin attacker geometry when positional samples are missing', () => {
  render(<IncidentReview touchStart={3.5} touchEnd={3.62} samples={[]} />);
  expect(screen.getByRole('region', { name: /incident review/i })).toBeTruthy();
  expect(screen.getByText(/positional samples unavailable/i)).toBeTruthy();
  expect(screen.queryByText(/attackerX=0/)).toBeNull();
  expect(screen.queryByText(/line=0/)).toBeNull();
});
