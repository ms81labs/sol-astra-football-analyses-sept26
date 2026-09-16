import { expect, it } from 'vitest';

import type { BackendEvent } from '../types';

it('keeps frontend event types aligned with additive DetectedEvent fields', () => {
  const event: BackendEvent = {
    type: 'shot',
    frameId: 12,
    timestamp: 12.4,
    description: 'provisional shot',
    reviewStatus: 'unreviewed',
    heuristicName: 'provisional_event_suggestion',
    evidenceVersion: 'evidence_v1',
    intervalStart: 12.0,
    intervalEnd: 13.0,
  };
  expect(event.evidenceVersion).toBe('evidence_v1');
  expect(event.intervalStart).toBe(12.0);
  expect(event.intervalEnd).toBe(13.0);
});
