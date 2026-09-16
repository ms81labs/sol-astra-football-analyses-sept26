import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import DrawingToolbar from './DrawingToolbar';

afterEach(cleanup);

describe('DrawingToolbar keyboard focus', () => {
  it('exposes each drawing mode as a pressed toggle', () => {
    render(
      <DrawingToolbar
        activeMode="arrow"
        onArrow={vi.fn()}
        onCircle={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'Arrow' }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: 'Circle' }).getAttribute('aria-pressed')).toBe('false');
  });

  it('returns focus to the persistent Arrow control after keyboard Cancel', () => {
    const onCancel = vi.fn();

    function Harness() {
      const [activeMode, setActiveMode] = useState<'circle' | null>('circle');
      return (
        <DrawingToolbar
          activeMode={activeMode}
          onArrow={vi.fn()}
          onCircle={vi.fn()}
          onCancel={() => {
            onCancel();
            setActiveMode(null);
          }}
        />
      );
    }

    render(<Harness />);
    expect(screen.getAllByRole('button').map((button) => button.textContent)).toEqual([
      'Arrow',
      'Circle',
      'Cancel',
    ]);
    const cancel = screen.getByRole('button', { name: 'Cancel' });
    cancel.focus();
    fireEvent.click(cancel, { detail: 0 });

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: 'Cancel' })).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Arrow' }));
    expect(document.activeElement).not.toBe(document.body);
  });
});
