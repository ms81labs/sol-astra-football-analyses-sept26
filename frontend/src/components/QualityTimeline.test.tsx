import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';

import QualityTimeline from './QualityTimeline';

it('orders high-impact uncertainty first and does not treat it as accepted', () => {
  render(
    <QualityTimeline
      items={[
        { id: 'possession', label: 'ambiguous possession around a shot', impact: 'high' },
        { id: 'team', label: 'incorrect team selection', impact: 'high' },
        { id: 'far', label: 'far-side miss', impact: 'medium' },
      ]}
    />,
  );
  const buttons = screen.getAllByRole('listitem');
  expect(buttons[0].textContent).toMatch(/incorrect team selection|ambiguous possession/i);
  expect(screen.getByText(/review first/i)).toBeTruthy();
});
