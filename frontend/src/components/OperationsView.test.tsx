import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';

import OperationsView from './OperationsView';

it('shows job phase, spend, retries and cleanup without treating cancel as termination', () => {
  render(
    <OperationsView
      phase="running"
      estimatedCost={2.0}
      actualCost={0.4}
      retries={1}
      cleanupResult="unknown"
      cancelRequested
    />,
  );
  expect(screen.getByText(/operations/i)).toBeTruthy();
  expect(screen.getByText(/running/i)).toBeTruthy();
  expect(screen.getByText(/estimated 2/i)).toBeTruthy();
  expect(screen.getByText(/actual 0.4/i)).toBeTruthy();
  expect(screen.getByText(/retries 1/i)).toBeTruthy();
  expect(screen.getByText(/cleanup unknown/i)).toBeTruthy();
  expect(screen.getByText(/cancellation is a request, not proof of termination/i)).toBeTruthy();
  expect(screen.getByText(/gpu inference does not run inside an http request/i)).toBeTruthy();
});
