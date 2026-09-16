import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import DemoMatchIssuePanel from './DemoMatchIssuePanel';
import type { MatchIssue } from '../types';

afterEach(cleanup);

describe('DemoMatchIssuePanel', () => {
  it('keeps issue text when saving fails', async () => {
    const onCreateIssue = vi.fn().mockResolvedValue(null);

    render(
      <DemoMatchIssuePanel
        issues={[]}
        currentFrame={12}
        currentTimestamp={2.4}
        reviewRange={null}
        processingBackend="local"
        onCreateIssue={onCreateIssue}
        onSeekToIssue={vi.fn()}
        onDeleteIssue={vi.fn()}
      />,
    );

    const textarea = screen.getByLabelText(/what went wrong/i) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Tracker lost the ball' } });
    fireEvent.click(screen.getByRole('button', { name: /log issue/i }));

    await waitFor(() => expect(onCreateIssue).toHaveBeenCalledOnce());
    expect(textarea.value).toBe('Tracker lost the ball');
  });

  it('disables issue submission until the save succeeds', async () => {
    let resolveSave: (value: MatchIssue) => void = () => {};
    const onCreateIssue = vi.fn(
      () => new Promise<MatchIssue>((resolve) => {
        resolveSave = resolve;
      }),
    );

    render(
      <DemoMatchIssuePanel
        issues={[]}
        currentFrame={12}
        currentTimestamp={2.4}
        reviewRange={null}
        processingBackend="local"
        onCreateIssue={onCreateIssue}
        onSeekToIssue={vi.fn()}
        onDeleteIssue={vi.fn()}
      />,
    );

    const textarea = screen.getByLabelText(/what went wrong/i) as HTMLTextAreaElement;
    const submitButton = screen.getByRole('button', { name: /log issue/i }) as HTMLButtonElement;
    fireEvent.change(textarea, { target: { value: 'Tracker lost the ball' } });
    fireEvent.click(submitButton);

    expect(submitButton.disabled).toBe(true);
    expect(textarea.disabled).toBe(true);
    for (const select of screen.getAllByRole('combobox')) {
      expect((select as HTMLSelectElement).disabled).toBe(true);
    }
    fireEvent.click(submitButton);
    expect(onCreateIssue).toHaveBeenCalledOnce();
    expect(textarea.value).toBe('Tracker lost the ball');

    resolveSave({
      id: 'issue-1',
      matchId: 'match-1',
      bucket: 'tracking_failure',
      frameStart: 12,
      frameEnd: 12,
      timestampStart: 2.4,
      timestampEnd: 2.4,
      processingBackend: 'local',
      evidenceTarget: 'product_bug',
      note: 'Tracker lost the ball',
      createdAt: '2026-09-10T00:00:00Z',
      updatedAt: '2026-09-10T00:00:00Z',
    });

    await waitFor(() => expect(textarea.value).toBe(''));
    expect(submitButton.disabled).toBe(false);
  });

  it('retains issue text and restores controls when the callback rejects', async () => {
    const onCreateIssue = vi.fn().mockRejectedValue(new Error('Save rejected.'));

    render(
      <DemoMatchIssuePanel
        issues={[]}
        currentFrame={12}
        currentTimestamp={2.4}
        reviewRange={null}
        processingBackend="local"
        onCreateIssue={onCreateIssue}
        onSeekToIssue={vi.fn()}
        onDeleteIssue={vi.fn()}
      />,
    );

    const textarea = screen.getByLabelText(/what went wrong/i) as HTMLTextAreaElement;
    const submitButton = screen.getByRole('button', { name: /log issue/i }) as HTMLButtonElement;
    const selects = screen.getAllByRole('combobox') as HTMLSelectElement[];
    fireEvent.change(textarea, { target: { value: 'Keep rejected issue' } });
    fireEvent.click(submitButton);

    expect(submitButton.disabled).toBe(true);
    await waitFor(() => expect(submitButton.disabled).toBe(false));
    expect(textarea.value).toBe('Keep rejected issue');
    expect(textarea.disabled).toBe(false);
    for (const select of selects) expect(select.disabled).toBe(false);
  });
});
