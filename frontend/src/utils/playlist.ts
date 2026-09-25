import { commandState, type CommandReceipt } from './commandLifecycle';

export interface PlaylistClip {
  generationId?: string;
  start: number;
  end: number;
  title?: string;
  notes: string;
  sourceEndFrameExclusive: number;
}

export function clipKey(clip: PlaylistClip): string {
  return `${clip.start}-${clip.end}-${clip.sourceEndFrameExclusive}-${clip.title ?? ''}-${clip.notes}`;
}

export function playlistClipsFromCorrections(
  items: CommandReceipt[],
  includedCommandIds?: readonly string[],
  generationId?: string,
): PlaylistClip[] {
  if (includedCommandIds) {
    const included = new Set(includedCommandIds);
    items = items.filter((item) => included.has(item.commandId ?? item.correctionId));
  }
  const undone = new Set(
    items
      .filter((item) => commandState(item) === 'applied')
      .map((item) => item.undoOf)
      .filter((undoOf): undoOf is string => typeof undoOf === 'string' && undoOf.length > 0),
  );
  const clips: PlaylistClip[] = [];
  for (const item of items) {
    if (item.kind !== 'playlist_item' || commandState(item) !== 'applied' || item.undoOf || undone.has(item.correctionId)) {
      continue;
    }
    const payload = item.payload ?? {};
    const start = Number(payload.timestampStart ?? payload.start);
    const end = Number(payload.timestampEnd ?? payload.end);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) continue;
    const exclusive = Number(payload.sourceEndFrameExclusive);
    clips.push({
      ...(generationId ? { generationId } : {}),
      start,
      end,
      title: typeof payload.title === 'string' ? payload.title : '',
      notes: typeof payload.notes === 'string' ? payload.notes : '',
      sourceEndFrameExclusive: Number.isFinite(exclusive) ? exclusive : 0,
    });
  }
  return clips;
}
