import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import ChangeHistory from './ChangeHistory';

afterEach(cleanup);

it('shows an undoable change history without rewriting the original correction', () => {
  const onUndo = vi.fn();
  render(
    <ChangeHistory
      items={[
        { correctionId: 'c1', kind: 'team_mapping', saveState: 'saved', undoOf: null },
        { correctionId: 'c2', kind: 'team_mapping', saveState: 'saved', undoOf: 'c1' },
      ]}
      onUndo={onUndo}
    />,
  );
  expect(screen.getByText(/undoable change history/i)).toBeTruthy();
  expect(screen.getByText(/original correction retained/i)).toBeTruthy();
  expect(screen.getByText('c1')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Undo c1' }));
  expect(onUndo).toHaveBeenCalledWith('c1');
});
