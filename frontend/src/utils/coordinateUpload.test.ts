import { afterEach, describe, expect, it, vi } from 'vitest';
import type { CoordinateConvention, UploadConfig } from '../types';
import { createMatchUpload, updateMatchConfig } from './api';

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

const conventions: CoordinateConvention[] = [
  { schemaVersion: 1, space: 'source_pixels', sourceWidth: 1920, sourceHeight: 1080, streamId: 'main',
    sourceFromObservation: [[2, 0, 100], [0, 2, 40], [0, 0, 1]] },
  { schemaVersion: 1, space: 'pitch_metres', pitchLengthM: 100, pitchWidthM: 60 },
  { schemaVersion: 1, space: 'pitch_normalized_0_100', axes: 'x_right_y_down', origin: 'top_left' },
  { schemaVersion: 1, space: 'unknown' },
];

describe('C02 declared coordinate upload contract', () => {
  it.each(conventions)('preserves the declared $space without inferred projection', async (coordinateConvention) => {
    const request = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ matchId: 'm', jobId: 'j', status: 'queued' }) });
    vi.stubGlobal('fetch', request);
    const config: UploadConfig = { coordinateConvention };
    await createMatchUpload({ name: 'Coordinates', inputMode: 'tracking_json', file: new File(['[]'], 'tracking.json'), config });
    const form = (request.mock.calls[0][1] as RequestInit).body as FormData;
    expect(JSON.parse(String(form.get('config')))).toEqual(config);
    expect(request).toHaveBeenCalledTimes(1);
  });

  it('keeps explicit unknown distinct from an omitted legacy convention in versioned config', async () => {
    const request = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ generationId: 'g2' }) });
    vi.stubGlobal('fetch', request);
    const payload = { coordinateConvention: conventions[3], commandId: 'coordinate-edit', baseGeneration: 'g1' };
    await updateMatchConfig('m', payload);
    expect(JSON.parse((request.mock.calls[0][1] as RequestInit).body as string)).toEqual(payload);
    expect(request).toHaveBeenCalledTimes(1);
  });
});
