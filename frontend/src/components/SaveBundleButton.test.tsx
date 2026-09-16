import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import SaveBundleButton from './SaveBundleButton';
import * as api from '../utils/api';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('opens a named native modal, focuses its name, dismisses on Escape, and restores focus', () => {
  const showModal = vi.spyOn(HTMLDialogElement.prototype, 'showModal');
  render(<SaveBundleButton currentFrame={0} events={[]} />);
  const opener = screen.getByRole('button', { name: 'Save Playlist' });
  opener.focus();
  fireEvent.click(opener);
  const dialog = screen.getByRole('dialog', { name: 'Save Review Playlist' });
  expect(showModal).toHaveBeenCalledOnce();
  expect(document.activeElement).toBe(within(dialog).getByLabelText(/Name/));
  fireEvent(dialog, new Event('cancel', { bubbles: false, cancelable: true }));
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(document.activeElement).toBe(opener);
});

it('saves through the existing bundle API and restores focus after success', async () => {
  const createBundle = vi.spyOn(api, 'createBundle').mockResolvedValue({ id: 'b' } as Awaited<ReturnType<typeof api.createBundle>>);
  const onSave = vi.fn();
  render(<SaveBundleButton currentFrame={3} events={[]} onSave={onSave} />);
  const opener = screen.getByRole('button', { name: 'Save Playlist' });
  opener.focus();
  fireEvent.click(opener);
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Save Playlist' }));
  await waitFor(() => expect(onSave).toHaveBeenCalledWith('b'));
  expect(createBundle).toHaveBeenCalledOnce();
  await waitFor(() => expect(document.activeElement).toBe(opener));
});
