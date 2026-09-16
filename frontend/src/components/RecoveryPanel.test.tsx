import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import RecoveryPanel from './RecoveryPanel';

afterEach(cleanup);

it('exposes access deletion, unresolved incidents and unmeasured recovery objectives', () => {
  const onDelete = vi.fn();
  render(
    <RecoveryPanel
      controllerRecorded={false}
      unresolvedIncidents={[{ id: 'inc-1', title: 'cleanup unconfirmed' }]}
      recoveryObjectivesDefined={false}
      onRequestDeletion={onDelete}
    />,
  );
  expect(screen.getByText(/access\/deletion/i)).toBeTruthy();
  expect(screen.getByText(/track IDs do not anonymise identifiable video/i)).toBeTruthy();
  expect(screen.getByText(/operator-visible unresolved incidents/i)).toBeTruthy();
  expect(screen.getByText(/cleanup unconfirmed/i)).toBeTruthy();
  expect(screen.getByText(/recovery objectives remain unmeasured/i)).toBeTruthy();
  expect(screen.queryByText(/enterprise uptime/i)).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: /request deletion/i }));
  expect(onDelete).toHaveBeenCalled();
});
