import { useState } from 'react';

import { clipKey, type PlaylistClip } from '../utils/playlist';
import { assembleMatchReport, exportPlaylistInterval } from '../utils/workbench';

interface PlaylistBuilderProps {
  matchId?: string;
  reviewRange?: { startFrame: number; endFrame: number } | null;
  frames?: Array<{ Frame_ID: number; Timestamp: number }>;
  sourceFps?: number;
  storedClips?: PlaylistClip[];
  onClipSaved?: (clip: PlaylistClip) => void | Promise<void>;
  onOpenInterval?: (sourceStartSeconds: number) => void;
}

function markedIntervalSeconds(
  range: { startFrame: number; endFrame: number },
  frames: Array<{ Frame_ID: number; Timestamp: number }>,
  sourceFps: number,
): { start: number; end: number } | null {
  if (frames.length === 0 || !(sourceFps > 0)) return null;
  const byId = new Map(frames.map((frame) => [frame.Frame_ID, frame.Timestamp]));
  const start = byId.get(range.startFrame);
  const endInclusive = byId.get(range.endFrame);
  if (start == null || endInclusive == null) return null;
  const next = frames.find((frame) => frame.Frame_ID > range.endFrame);
  const end = next != null ? next.Timestamp : endInclusive + 1 / sourceFps;
  if (!(end >= start)) return null;
  return { start, end };
}

export default function PlaylistBuilder({
  matchId,
  reviewRange = null,
  frames = [],
  sourceFps = 25,
  storedClips = [],
  onClipSaved,
  onOpenInterval,
}: PlaylistBuilderProps) {
  const rangeKey = reviewRange ? `${reviewRange.startFrame}:${reviewRange.endFrame}:${sourceFps}` : '';
  const marked = reviewRange ? markedIntervalSeconds(reviewRange, frames, sourceFps) : null;
  const [draft, setDraft] = useState({ key: '', start: '12', end: '14' });
  const start = marked && draft.key !== rangeKey ? String(marked.start) : draft.start;
  const end = marked && draft.key !== rangeKey ? String(marked.end) : draft.end;
  const [notes, setNotes] = useState('');
  const [clips, setClips] = useState<PlaylistClip[]>([]);
  const [exportError, setExportError] = useState<string | null>(null);
  const [reportNote, setReportNote] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  async function addClip() {
    const from = Number(start);
    const to = Number(end);
    if (!Number.isFinite(from) || !Number.isFinite(to) || to < from) return;
    try {
      const interval = await exportPlaylistInterval(from, to, sourceFps);
      setExportError(null);
      const clip: PlaylistClip = {
        start: interval.sourceStartSeconds,
        end: interval.sourceEndSeconds,
        notes,
        sourceEndFrameExclusive: interval.sourceEndFrameExclusive,
      };
      if (onClipSaved) {
        await onClipSaved(clip);
      } else {
        setClips((current) => [...current, clip]);
      }
      onOpenInterval?.(clip.start);
    } catch (error) {
      setExportError(error instanceof Error ? error.message : 'Failed to export playlist interval');
    }
  }

  async function assembleReport() {
    if (!matchId) return;
    try {
      const report = await assembleMatchReport(matchId);
      setReportError(null);
      const notesForReport: string[] = [];
      if (report.publication?.wholeMatchFrequency === false) {
        notesForReport.push('does not claim whole-match frequency');
      }
      if (report.publication?.frequencyRequiresDenominator) {
        notesForReport.push('frequency requires a denominator');
      }
      setReportNote(notesForReport.join('. ') || 'Report assembled');
    } catch (error) {
      setReportError(error instanceof Error ? error.message : 'Failed to assemble report');
    }
  }

  return (
    <section aria-label="Playlist builder" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Playlist / report builder</h4>
      <label className="block text-xs text-slate-400">
        Clip start
        <input
          value={start}
          onChange={(event) => setDraft({ key: rangeKey, start: event.target.value, end })}
          className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200"
        />
      </label>
      <label className="block text-xs text-slate-400">
        Clip end
        <input
          value={end}
          onChange={(event) => setDraft({ key: rangeKey, start, end: event.target.value })}
          className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200"
        />
      </label>
      <label className="block text-xs text-slate-400">
        Notes
        <input value={notes} onChange={(event) => setNotes(event.target.value)} className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
      </label>
      <button type="button" onClick={() => void addClip()} className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white">
        Add clip
      </button>
      {matchId ? (
        <button type="button" onClick={() => void assembleReport()} className="ml-2 px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white">
          Assemble report
        </button>
      ) : null}
      {exportError && <p className="text-xs text-amber-200">{exportError}</p>}
      {reportError && <p className="text-xs text-amber-200">{reportError}</p>}
      {[...storedClips, ...clips].filter((clip, index, all) => all.findIndex((other) => clipKey(other) === clipKey(clip)) === index).map((clip) => (
        <p key={clipKey(clip)} className="text-xs text-slate-300">
          {clip.start}s to {clip.end}s (frame {clip.sourceEndFrameExclusive} exclusive){clip.notes ? ` · ${clip.notes}` : ''}
        </p>
      ))}
      {reportNote && <p className="text-xs text-slate-300">{reportNote}</p>}
      <p className="text-xs text-slate-500">Reviewed passages do not establish a whole-match frequency.</p>
    </section>
  );
}
