import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';

import ReleaseGate from './ReleaseGate';

afterEach(cleanup);

it('refuses public exposure before security review and keeps decoder and egress constrained', () => {
  render(<ReleaseGate />);
  expect(screen.getByText(/no public exposure before the required security review/i)).toBeTruthy();
  expect(screen.getByText(/protocol and network allowlist/i)).toBeTruthy();
  expect(screen.getByText(/constrained decoder/i)).toBeTruthy();
  expect(screen.getByText(/worker egress is deny-by-default/i)).toBeTruthy();
  expect(screen.getByText(/least privilege storage/i)).toBeTruthy();
  expect(screen.queryByText(/public hosted deployment accepted/i)).toBeNull();
});
