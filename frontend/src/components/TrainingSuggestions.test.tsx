import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';

import TrainingSuggestions from './TrainingSuggestions';

it('combines accepted observations with drills and does not prescribe medical load', () => {
  render(
    <TrainingSuggestions
      observations={[{ id: 'o1', label: 'near-side recovery' }]}
      drills={[{ name: 'near-side recovery 2v2', coachReviewed: true }]}
    />,
  );
  expect(screen.getByText(/near-side recovery 2v2/)).toBeTruthy();
  expect(screen.getByText(/near-side recovery$/)).toBeTruthy();
  expect(screen.getByText(/does not prescribe medical load/i)).toBeTruthy();
  expect(screen.queryByText(/diagnose fatigue or injury as a medical claim/i)).toBeNull();
});
