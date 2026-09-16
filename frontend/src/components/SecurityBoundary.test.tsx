import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';

import SecurityBoundary from './SecurityBoundary';

afterEach(cleanup);

it('treats model output as untrusted and refuses secrets in artifacts', () => {
  render(<SecurityBoundary />);
  expect(screen.getByText(/model output is untrusted/i)).toBeTruthy();
  expect(screen.getByText(/allowlisted actions/i)).toBeTruthy();
  expect(screen.getByText(/no secrets in artifacts/i)).toBeTruthy();
  expect(screen.getByText(/signed and scoped job access/i)).toBeTruthy();
  expect(screen.queryByText(/authenticated hosted deployment/i)).toBeNull();
});
