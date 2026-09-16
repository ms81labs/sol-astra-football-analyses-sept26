import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';

import NativePackaging from './NativePackaging';

afterEach(cleanup);

it('keeps native wheels unportable and custom native code unapproved', () => {
  render(<NativePackaging />);
  expect(screen.getByText(/native wheels are not universally portable/i)).toBeTruthy();
  expect(screen.getByText(/macos and ubuntu profiles are tested independently/i)).toBeTruthy();
  expect(screen.getByText(/exact ffmpeg build/i)).toBeTruthy();
  expect(screen.getByText(/no rpc fleet/i)).toBeTruthy();
  expect(screen.getByText(/custom native code remains unapproved/i)).toBeTruthy();
  expect(screen.queryByText(/rust rewrite accepted/i)).toBeNull();
});
