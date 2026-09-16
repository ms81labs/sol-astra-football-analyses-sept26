import { useState } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { FrameData, PlayerProfile } from '../types';
import TacticalPitch from './TacticalPitch';

const frame: FrameData = {
  Frame_ID: 12,
  Timestamp: 4.8,
  Ball: null,
  My_Team: [{ id: 7, x: 25, y: 40, conf: 0.9 }],
  Enemies: [{ enemy_id: 7, x: 70, y: 55, conf: 0.8 }],
};

function profile(team: PlayerProfile['team'], playerId: number): PlayerProfile {
  return {
    team,
    playerId,
    passes: 1,
    crosses: 0,
    throughBalls: 0,
    shots: 0,
    tacklesWon: 0,
    recoveries: 0,
    interceptions: 0,
    ballWins: 0,
    involvements: 1,
    xgCreated: 0,
    xgTaken: 0,
    impactScore: 1,
    avgX: team === 'my_team' ? 25 : 70,
    avgY: team === 'my_team' ? 40 : 55,
    totalDistance: 10,
    topSpeed: 20,
    profileLabel: `${team} ${playerId}`,
    summaryLine: 'Current player',
  };
}

const mySeven = profile('my_team', 7);
const enemySeven = profile('enemy', 7);
const absentPlayer = profile('my_team', 8);

function submitCoordinates(x: string, y: string) {
  const xInput = screen.getByLabelText(/ X$/);
  xInput.focus();
  fireEvent.change(xInput, { target: { value: x } });
  fireEvent.change(screen.getByLabelText(/ Y$/), { target: { value: y } });
  fireEvent.submit(xInput.closest('form')!);
}

beforeEach(() => {
  const context = {
    scale: vi.fn(),
    fillRect: vi.fn(),
    strokeRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    fillText: vi.fn(),
    closePath: vi.fn(),
    setLineDash: vi.fn(),
  };
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLCanvasElement.prototype, 'getBoundingClientRect').mockReturnValue({
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: 100,
    bottom: 100,
    width: 100,
    height: 100,
    toJSON: () => ({}),
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('TacticalPitch keyboard controls', () => {
  it('names and describes the visual canvas', () => {
    render(<TacticalPitch frameData={frame} />);

    const canvas = screen.getByRole('img', { name: 'Tactical pitch' });
    const descriptionId = canvas.getAttribute('aria-describedby');
    expect(descriptionId).toBeTruthy();
    expect(document.getElementById(descriptionId!)).not.toBeNull();
    expect(canvas.textContent).toContain('Player and ball positions are drawn on this pitch.');
  });

  it('selects the exact current-frame profile by team and player identity', () => {
    const onPlayerClick = vi.fn();
    render(
      <TacticalPitch
        frameData={frame}
        playerProfiles={[mySeven, enemySeven, absentPlayer]}
        onPlayerClick={onPlayerClick}
      />,
    );

    const select = screen.getByRole('combobox', { name: 'Current-frame player' });
    expect(Array.from((select as HTMLSelectElement).options).map((option) => option.value)).toEqual([
      '',
      'my_team:7',
      'enemy:7',
    ]);
    fireEvent.change(select, { target: { value: 'enemy:7' } });

    expect(onPlayerClick).toHaveBeenCalledWith(enemySeven);
  });

  it('submits circle coordinates with the same callback payload as the pointer path', () => {
    const onAnnotationCreate = vi.fn();
    render(
      <TacticalPitch
        frameData={frame}
        drawingMode="circle"
        pitchAnnotationPlacementMode="circle"
        onAnnotationCreate={onAnnotationCreate}
      />,
    );

    const canvas = screen.getByRole('img', { name: 'Tactical pitch' });
    fireEvent.mouseDown(canvas, { clientX: 25, clientY: 40 });
    fireEvent.mouseUp(canvas, { clientX: 25, clientY: 40 });
    const pointerPayload = onAnnotationCreate.mock.calls[0];
    onAnnotationCreate.mockClear();

    submitCoordinates('25', '40');

    expect(onAnnotationCreate).toHaveBeenCalledWith(...pointerPayload);
  });

  it('uses the existing staged arrow placement for keyboard start and end points', () => {
    const onAnnotationCreate = vi.fn();

    function ArrowHarness() {
      const [placementMode, setPlacementMode] = useState<'arrow-start' | 'arrow-end' | null>('arrow-start');
      return (
        <TacticalPitch
          frameData={frame}
          playerProfiles={[mySeven]}
          onPlayerClick={vi.fn()}
          drawingMode={placementMode ? 'arrow' : null}
          pitchAnnotationPlacementMode={placementMode}
          onAnnotationCreate={(...payload) => {
            onAnnotationCreate(...payload);
            setPlacementMode((current) => current === 'arrow-start' ? 'arrow-end' : null);
          }}
        />
      );
    }

    render(<ArrowHarness />);
    submitCoordinates('10', '20');
    expect(screen.getByLabelText('Arrow end X')).toBeTruthy();
    submitCoordinates('80', '70');

    expect(onAnnotationCreate.mock.calls).toEqual([
      [10, 20, 10, 20],
      [80, 70, 80, 70],
    ]);
    expect(screen.queryByLabelText('Arrow end X')).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('combobox', { name: 'Current-frame player' }));
  });

  it('blocks empty, non-finite, and out-of-range coordinates', () => {
    const onAnnotationCreate = vi.fn();
    render(
      <TacticalPitch
        frameData={frame}
        drawingMode="circle"
        pitchAnnotationPlacementMode="circle"
        onAnnotationCreate={onAnnotationCreate}
      />,
    );

    submitCoordinates('', '20');
    submitCoordinates('-1', '20');
    submitCoordinates('20', '101');
    submitCoordinates('1e309', '20');

    expect(onAnnotationCreate).not.toHaveBeenCalled();
    expect(screen.getByRole('alert').textContent).toContain('between 0 and 100');
  });

  it('returns focus to the current-frame player control when placement is cancelled', () => {
    const { rerender } = render(
      <TacticalPitch
        frameData={frame}
        playerProfiles={[mySeven]}
        onPlayerClick={vi.fn()}
        drawingMode="circle"
        pitchAnnotationPlacementMode="circle"
        onAnnotationCreate={vi.fn()}
      />,
    );
    (screen.getByLabelText('Circle X') as HTMLInputElement).focus();

    rerender(
      <TacticalPitch
        frameData={frame}
        playerProfiles={[mySeven]}
        onPlayerClick={vi.fn()}
        drawingMode={null}
        pitchAnnotationPlacementMode={null}
        onAnnotationCreate={vi.fn()}
      />,
    );

    expect(document.activeElement).toBe(screen.getByRole('combobox', { name: 'Current-frame player' }));
  });

  it('does not steal newer focus when an async save exits placement mode', async () => {
    let finishSave!: () => void;
    const save = new Promise<void>((resolve) => {
      finishSave = resolve;
    });

    function AsyncSaveHarness() {
      const [placementMode, setPlacementMode] = useState<'circle' | null>('circle');
      return (
        <>
          <button type="button">Persistent action</button>
          <TacticalPitch
            frameData={frame}
            playerProfiles={[mySeven]}
            onPlayerClick={vi.fn()}
            drawingMode={placementMode}
            pitchAnnotationPlacementMode={placementMode}
            onAnnotationCreate={() => {
              void save.then(() => setPlacementMode(null));
            }}
          />
        </>
      );
    }

    render(<AsyncSaveHarness />);
    submitCoordinates('25', '40');
    const persistentAction = screen.getByRole('button', { name: 'Persistent action' });
    persistentAction.focus();

    await act(async () => {
      finishSave();
      await save;
    });

    expect(document.activeElement).toBe(persistentAction);
  });
});


it('hit-tests current positions and excludes absent profiles', () => {
  const onPlayerClick = vi.fn();
  const moved = { ...mySeven, avgX: 80, avgY: 80 };
  render(<TacticalPitch frameData={frame} playerProfiles={[absentPlayer, moved, enemySeven]} onPlayerClick={onPlayerClick} />);
  fireEvent.click(screen.getByRole('img'), { clientX: 25, clientY: 40 });
  expect(onPlayerClick).toHaveBeenCalledWith(moved);
});

it('draws saved circles only inside their inclusive timestamp range', () => {
  const annotation = { id: 'a', matchId: 'm', type: 'circle' as const, frameStart: 0, frameEnd: 1, timestampStart: 4, timestampEnd: 5, x: 20, y: 30, createdAt: '', updatedAt: '' };
  const { rerender } = render(<TacticalPitch frameData={frame} savedAnnotations={[annotation]} />);
  const context = (screen.getByRole('img') as HTMLCanvasElement).getContext('2d')!;
  expect(context.arc).toHaveBeenCalledWith(20, 30, 20, 0, Math.PI * 2);
  vi.mocked(context.arc).mockClear();
  rerender(<TacticalPitch frameData={{ ...frame, Timestamp: 20 }} savedAnnotations={[annotation]} />);
  expect(vi.mocked(context.arc).mock.calls.some(call => call[2] === 20)).toBe(false);
});
