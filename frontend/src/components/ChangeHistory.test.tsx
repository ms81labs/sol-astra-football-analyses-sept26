import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import ChangeHistory from './ChangeHistory';
afterEach(cleanup);
const original = { correctionId: 'c1', kind: 'team_mapping', saveState: 'saved', applyState: 'applied' as const, appliedGeneration: 'g1', undoOf: null };
it('shows an undoable applied change without rewriting the original correction', () => {
  const onUndo = vi.fn();
  render(<ChangeHistory items={[original]} onUndo={onUndo} />);
  expect(screen.getByText(/undoable change history/i)).toBeTruthy();
  expect(screen.getByText(/original correction retained/i)).toBeTruthy();
  expect(screen.getByText('c1')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Undo c1' }));
  expect(onUndo).toHaveBeenCalledWith('c1');
});
it('retains history but does not advertise undo of a recorded or already undone effect', () => {
  render(<ChangeHistory items={[original,
    { ...original, correctionId: 'c2', kind: 'undo', undoOf: 'c1', appliedGeneration: 'g2' },
    { ...original, correctionId: 'pending', applyState: 'committed' },
  ]} onUndo={vi.fn()} />);
  expect(screen.getByText('c1')).toBeTruthy();
  expect(screen.queryByRole('button', { name: /undo c[12]|undo pending/i })).toBeNull();
  expect(screen.getByText('pending').closest('li')?.textContent.includes('recorded')).toBeTruthy();
});
