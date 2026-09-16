import { useState } from 'react';

import { fetchMatchDerivedDistance, submitMatchCalibration } from '../utils/workbench';

interface HoldoutCalibrationPanelProps {
  matchId?: string;
}

export default function HoldoutCalibrationPanel({ matchId }: HoldoutCalibrationPanelProps) {
  const [imageX, setImageX] = useState('');
  const [imageY, setImageY] = useState('');
  const [pitchX, setPitchX] = useState('');
  const [pitchY, setPitchY] = useState('');
  const [holdoutNote, setHoldoutNote] = useState<string | null>(null);
  const [distanceNote, setDistanceNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function measureHoldout() {
    if (!matchId) return;
    const imageXValue = Number(imageX);
    const imageYValue = Number(imageY);
    const pitchXValue = Number(pitchX);
    const pitchYValue = Number(pitchY);
    if (![imageXValue, imageYValue, pitchXValue, pitchYValue].every(Number.isFinite)) return;
    try {
      const measured = await submitMatchCalibration(matchId, {
        landmarks: [{
          name: 'holdout',
          imageX: imageXValue,
          imageY: imageYValue,
          pitchX: pitchXValue,
          pitchY: pitchYValue,
          independentHoldout: true,
        }],
      });
      setError(null);
      setHoldoutNote(measured.evaluation?.accepted ? 'Holdout accepted' : 'Holdout not accepted');
      const distance = await fetchMatchDerivedDistance(matchId);
      if (distance.availability === 'available' && distance.value != null && distance.value !== 0) {
        setDistanceNote(`Derived distance ${distance.value} m`);
      } else {
        setDistanceNote('Derived distance withheld');
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to measure holdout');
    }
  }

  return (
    <section aria-label="Holdout calibration" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Independent holdout</h4>
      <p className="text-xs text-slate-500">Independent holdout landmarks check the stored homography. Four fit points are not holdout.</p>
      <label className="block text-xs text-slate-400">
        Image X
        <input value={imageX} onChange={(event) => setImageX(event.target.value)} className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
      </label>
      <label className="block text-xs text-slate-400">
        Image Y
        <input value={imageY} onChange={(event) => setImageY(event.target.value)} className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
      </label>
      <label className="block text-xs text-slate-400">
        Pitch X (m)
        <input value={pitchX} onChange={(event) => setPitchX(event.target.value)} className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
      </label>
      <label className="block text-xs text-slate-400">
        Pitch Y (m)
        <input value={pitchY} onChange={(event) => setPitchY(event.target.value)} className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
      </label>
      <button
        type="button"
        onClick={() => void measureHoldout()}
        disabled={!matchId}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Measure holdout
      </button>
      {error && <p className="text-xs text-amber-200">{error}</p>}
      {holdoutNote && <p className="text-xs text-slate-300">{holdoutNote}</p>}
      {distanceNote && <p className="text-xs text-slate-300">{distanceNote}</p>}
    </section>
  );
}
