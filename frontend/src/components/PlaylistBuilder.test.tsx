import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';

import PlaylistBuilder from './PlaylistBuilder';

it('exports time-bounded clips with notes and refuses whole-match frequency claims', () => {
  render(<PlaylistBuilder />);
  fireEvent.change(screen.getByLabelText(/clip start/i), { target: { value: '12' } });
  fireEvent.change(screen.getByLabelText(/clip end/i), { target: { value: '14' } });
  fireEvent.change(screen.getByLabelText(/notes/i), { target: { value: 'second-half turnover then shot' } });
  fireEvent.click(screen.getByRole('button', { name: /add clip/i }));
  expect(screen.getByText(/12s to 14s/)).toBeTruthy();
  expect(screen.getByText(/second-half turnover then shot/)).toBeTruthy();
  expect(screen.getByText(/do not establish a whole-match frequency/i)).toBeTruthy();
});
