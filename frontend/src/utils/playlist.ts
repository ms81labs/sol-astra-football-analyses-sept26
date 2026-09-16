export interface PlaylistClip {
  start: number;
  end: number;
  notes: string;
  sourceEndFrameExclusive: number;
}

export function clipKey(clip: PlaylistClip): string {
  return `${clip.start}-${clip.end}-${clip.sourceEndFrameExclusive}-${clip.notes}`;
}

export function playlistClipsFromCorrections(
  items: Array<{
    correctionId: string;
    kind: string;
    saveState: string;
    undoOf?: string | null;
    payload?: Record<string, unknown> | null;
  }>,
): PlaylistClip[] {
  const undone = new Set(
    items
      .map((item) => item.undoOf)
      .filter((undoOf): undoOf is string => typeof undoOf === 'string' && undoOf.length > 0),
  );
  const clips: PlaylistClip[] = [];
  for (const item of items) {
    if (item.kind !== 'playlist_item' || item.saveState !== 'saved' || item.undoOf || undone.has(item.correctionId)) {
      continue;
    }
    const payload = item.payload ?? {};
    const start = Number(payload.timestampStart ?? payload.start);
    const end = Number(payload.timestampEnd ?? payload.end);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) continue;
    const exclusive = Number(payload.sourceEndFrameExclusive);
    clips.push({
      start,
      end,
      notes: typeof payload.notes === 'string' ? payload.notes : '',
      sourceEndFrameExclusive: Number.isFinite(exclusive) ? exclusive : 0,
    });
  }
  return clips;
}
