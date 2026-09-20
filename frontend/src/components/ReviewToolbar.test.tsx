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

  it('dispatches review shortcuts without stealing typed note text', () => {
    const onShortcut = vi.fn();
    render(
      <ReviewToolbar
        onCreateNote={vi.fn()}
        onCreateTaggedMoment={vi.fn()}
        onShortcut={onShortcut}
      />,
    );
    fireEvent.keyDown(window, { key: 'a' });
    fireEvent.keyDown(window, { key: ' ' });
    fireEvent.keyDown(window, { key: '[' });
    expect(onShortcut).toHaveBeenCalledWith('accept');
    expect(onShortcut).toHaveBeenCalledWith('play_pause');
    expect(onShortcut).toHaveBeenCalledWith('previous_candidate');
    const input = screen.getByLabelText(/annotation text/i);
    fireEvent.keyDown(input, { key: 'a' });
    expect(onShortcut).toHaveBeenCalledTimes(3);
  });

  it('keeps the global shortcut listener stable while using the latest callback', () => {
    const addListener = vi.spyOn(window, 'addEventListener');
    const firstShortcut = vi.fn();
    const latestShortcut = vi.fn();
    const { rerender } = render(
      <ReviewToolbar
        onCreateNote={vi.fn()}
        onCreateTaggedMoment={vi.fn()}
        onShortcut={firstShortcut}
      />,
    );
    const initialKeydownListeners = addListener.mock.calls.filter(([type]) => type === 'keydown').length;

    rerender(
      <ReviewToolbar
        onCreateNote={vi.fn()}
        onCreateTaggedMoment={vi.fn()}
        onShortcut={latestShortcut}
      />,
    );

    expect(addListener.mock.calls.filter(([type]) => type === 'keydown')).toHaveLength(initialKeydownListeners);
    fireEvent.keyDown(window, { key: 'a' });
    expect(firstShortcut).not.toHaveBeenCalled();
    expect(latestShortcut).toHaveBeenCalledWith('accept');
    addListener.mockRestore();
  });

  it('shows pending, conflicted and unavailable correction save states', () => {
    const { rerender } = render(
      <ReviewToolbar onCreateNote={vi.fn()} onCreateTaggedMoment={vi.fn()} saveState="pending" />,
    );
    expect(screen.getByText(/edit pending/i)).toBeTruthy();
    rerender(
      <ReviewToolbar onCreateNote={vi.fn()} onCreateTaggedMoment={vi.fn()} saveState="conflicted" />,
    );
    expect(screen.getByText(/stale correction/i)).toBeTruthy();
    rerender(
      <ReviewToolbar onCreateNote={vi.fn()} onCreateTaggedMoment={vi.fn()} saveState="unavailable" />,
    );
    expect(screen.getByText(/application unconfirmed/i)).toBeTruthy();
    rerender(
      <ReviewToolbar onCreateNote={vi.fn()} onCreateTaggedMoment={vi.fn()} saveState="saved" />,
    );
    expect(screen.getByText(/edit recorded.*application not confirmed/i)).toBeTruthy();
  });
});
