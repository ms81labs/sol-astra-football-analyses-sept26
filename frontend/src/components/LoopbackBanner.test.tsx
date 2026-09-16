import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';

import LoopbackBanner from './LoopbackBanner';

afterEach(cleanup);

it('states that public and LAN access stay blocked until the network gate', () => {
  render(<LoopbackBanner deploymentBoundary="loopback" />);
  expect(screen.getByText(/loopback/i)).toBeTruthy();
  expect(screen.getByText(/public and LAN access remain blocked/i)).toBeTruthy();
  expect(screen.getByText(/origin\/host checks are not authentication/i)).toBeTruthy();
});
