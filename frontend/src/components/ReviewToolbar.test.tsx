import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import ReviewToolbar from './ReviewToolbar';
import type { TacticalAnnotation } from '../types';

afterEach(cleanup);

describe('ReviewToolbar', () => {
  it('keeps note text when saving fails', async () => {
    const onCreateNote = vi.fn().mockResolvedValue(null);

    render(<ReviewToolbar onCreateNote={onCreateNote} onCreateTaggedMoment={vi.fn()} />);

    const input = screen.getByLabelText(/annotation text/i) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Keep this note' } });
    fireEvent.click(screen.getByRole('button', { name: /note/i }));

    await waitFor(() => expect(onCreateNote).toHaveBeenCalledOnce());
    expect(input.value).toBe('Keep this note');
  });

  it('disables submission until a tagged moment is saved', async () => {
    let resolveSave: (value: TacticalAnnotation) => void = () => {};
    const onCreateTaggedMoment = vi.fn(
      () => new Promise<TacticalAnnotation>((resolve) => {
        resolveSave = resolve;
      }),
    );

    render(<ReviewToolbar onCreateNote={vi.fn()} onCreateTaggedMoment={onCreateTaggedMoment} />);

    const input = screen.getByLabelText(/annotation text/i) as HTMLInputElement;
    const tagButton = screen.getByRole('button', { name: /tag/i }) as HTMLButtonElement;
    fireEvent.change(input, { target: { value: 'Pressing trigger' } });
    fireEvent.click(tagButton);

    expect(tagButton.disabled).toBe(true);
    fireEvent.click(tagButton);
    expect(onCreateTaggedMoment).toHaveBeenCalledOnce();
    expect(input.value).toBe('Pressing trigger');

    resolveSave({
      id: 'annotation-1',
      matchId: 'match-1',
      type: 'moment',
      frameStart: 12,
      frameEnd: 12,
      timestampStart: 2.4,
      timestampEnd: 2.4,
      label: 'Pressing trigger',
      createdAt: '2026-09-10T00:00:00Z',
      updatedAt: '2026-09-10T00:00:00Z',
    });

    await waitFor(() => expect(input.value).toBe(''));
    expect(tagButton.disabled).toBe(false);
  });

  it('retains note text and restores controls when the callback rejects', async () => {
    const onCreateNote = vi.fn().mockRejectedValue(new Error('Save rejected.'));

    render(<ReviewToolbar onCreateNote={onCreateNote} onCreateTaggedMoment={vi.fn()} />);

    const input = screen.getByLabelText(/annotation text/i) as HTMLInputElement;
    const noteButton = screen.getByRole('button', { name: /note/i }) as HTMLButtonElement;
    fireEvent.change(input, { target: { value: 'Keep rejected note' } });
    fireEvent.click(noteButton);

    await waitFor(() => expect(noteButton.disabled).toBe(false));
    expect(input.value).toBe('Keep rejected note');
  });
});
