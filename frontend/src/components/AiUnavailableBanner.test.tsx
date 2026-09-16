import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';

import AiUnavailableBanner from './AiUnavailableBanner';

afterEach(cleanup);

it('keeps review, metrics and template reports available when providers are disabled', () => {
  render(<AiUnavailableBanner providersEnabled={false} />);
  expect(screen.getByText(/AI unavailable/i)).toBeTruthy();
  expect(screen.getByText(/review, metrics and template reports remain available/i)).toBeTruthy();
  expect(screen.queryByText(/concealing partial processing/i)).toBeNull();
});

it('hides the banner when a provider is enabled', () => {
  const { container } = render(<AiUnavailableBanner providersEnabled />);
  expect(container.firstChild).toBeNull();
});
