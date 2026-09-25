import { useEffect, useLayoutEffect, useRef, useState } from 'react';

import { clipKey, type PlaylistClip } from '../utils/playlist';
import { assembleMatchReport, exportPlaylistInterval, fetchMatchEdits, renderMatchEdit } from '../utils/workbench';

interface PlaylistBuilderProps {
  matchId?: string;
  generationId?: string;
  reviewRange?: { startFrame: number; endFrame: number } | null;
  sourceInterval?: { start: number; end: number; evidenceIds?: string[] } | null;
  frames?: Array<{ Frame_ID: number; Timestamp: number }>;
  sourceFps?: number;
  sampleFps?: number;
  videoAvailable?: boolean;
  storedClips?: PlaylistClip[];
  onClipSaved?: (clip: PlaylistClip) => void | Promise<void>;
  onClipUpdated?: (correctionId: string, title: string, notes: string) => void | Promise<void>;
  onOpenInterval?: (sourceStartSeconds: number) => void;
}

function markedIntervalSeconds(
  range: { startFrame: number; endFrame: number },
  frames: Array<{ Frame_ID: number; Timestamp: number }>,
  sourceFps: number,
  sampleFps: number,
): { start: number; end: number } | null {
  if (frames.length === 0 || !(sourceFps > 0) || !(sampleFps > 0)) return null;
  const byId = new Map(frames.map((frame) => [frame.Frame_ID, frame.Timestamp]));
  const start = byId.get(range.startFrame);
  const endInclusive = byId.get(range.endFrame);
  if (start == null || endInclusive == null) return null;
  const next = frames.find((frame) => frame.Frame_ID > range.endFrame);
  const end = next != null ? next.Timestamp : endInclusive + 1 / sampleFps;
  if (!(end >= start)) return null;
  return { start, end };
}

export default function PlaylistBuilder({
  matchId, generationId,
  reviewRange = null,
  sourceInterval = null,
  frames = [],
  sourceFps = 25,
  sampleFps = sourceFps,
  videoAvailable = false,
  storedClips = [],
  onClipSaved,
  onClipUpdated,
  onOpenInterval,
}: PlaylistBuilderProps) {
  const scopeVersion = useRef(0);
  useLayoutEffect(() => { scopeVersion.current += 1; return () => { scopeVersion.current += 1; }; }, [matchId, generationId]);
  const rangeKey = sourceInterval ? `${sourceInterval.start}:${sourceInterval.end}` : reviewRange ? `${reviewRange.startFrame}:${reviewRange.endFrame}:${sampleFps}` : '';
  const marked = sourceInterval ?? (reviewRange ? markedIntervalSeconds(reviewRange, frames, sourceFps, sampleFps) : null);
  const [draft, setDraft] = useState({ key: '', start: '12', end: '14' });
  const [editing, setEditing] = useState<{ matchId?: string; generationId?: string; clip: PlaylistClip } | null>(null);
  const editingClip = editing && editing.matchId === matchId && editing.generationId === generationId ? editing.clip : null;
  const start = editingClip ? String(editingClip.start) : marked && draft.key !== rangeKey ? String(marked.start) : draft.start;
  const end = editingClip ? String(editingClip.end) : marked && draft.key !== rangeKey ? String(marked.end) : draft.end;
  const [title, setTitle] = useState('');
  const [notes, setNotes] = useState('');
  const [clips, setClips] = useState<PlaylistClip[]>([]);
  const [exportError, setExportError] = useState<string | null>(null);
  const [reportNote, setReportNote] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [editNote, setEditNote] = useState<string | null>(null);
  const [renderNote, setRenderNote] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchEdits(matchId, generationId)
      .then((payload) => {
        if (cancelled) return;
        if (payload.reencodeFullMatch === false && payload.renderOnDemand === true) {
          setEditNote('Source-linked playlist: render on demand and does not re-encode the full match.');
        } else {
          setEditNote(null);
        }
      })
      .catch(() => {
        if (!cancelled) setEditNote(null);
      });
    return () => {
      cancelled = true;
    };
  }, [matchId, generationId, storedClips.length]);

  async function addClip() {
    const operation = scopeVersion.current;
    if (editingClip) {
      if (!editingClip.correctionId || !onClipUpdated) return;
      try {
        await onClipUpdated(editingClip.correctionId, title.trim(), notes);
        if (operation !== scopeVersion.current) return;
        setExportError(null);
        setEditing(null);
      } catch (error) {
        if (operation === scopeVersion.current) setExportError(error instanceof Error ? error.message : 'Failed to edit clip');
      }
      return;
    }
    const from = Number(start);
    const to = Number(end);
    if (!Number.isFinite(from) || !Number.isFinite(to) || to < from) return;
    try {
      const interval = await exportPlaylistInterval(from, to, sourceFps);
      if (operation !== scopeVersion.current) return;
      setExportError(null);
      const clip: PlaylistClip = {
        ...(generationId ? { generationId } : {}),
        start: interval.sourceStartSeconds,
        end: interval.sourceEndSeconds,
        title: title.trim(),
        notes,
        ...(sourceInterval?.evidenceIds?.length && interval.sourceStartSeconds <= sourceInterval.start
          && sourceInterval.start < interval.sourceEndSeconds && sourceInterval.end <= interval.sourceEndSeconds
          ? { evidenceIds: sourceInterval.evidenceIds } : {}),
        sourceEndFrameExclusive: interval.sourceEndFrameExclusive,
      };
      if (onClipSaved) {
        await onClipSaved(clip);
      } else {
        setClips((current) => [...current, clip]);
      }
      if (operation !== scopeVersion.current) return;
      onOpenInterval?.(clip.start);
      if (matchId) {
        try {
          const rendered = await renderMatchEdit(matchId, clip.start, clip.end, generationId);
          if (operation !== scopeVersion.current) return;
          if (generationId && rendered.generationId !== generationId) throw new Error('Playlist generation changed; refresh before rendering.');
          if (rendered.reencodedFullMatch === false) {
            setRenderNote(rendered.executionStatus === 'not_run' ? 'Source interval prepared; media rendering has not run.' : 'Rendered interval on demand. reencodedFullMatch is false.');
          } else {
            setRenderNote(null);
          }
        } catch {
          if (operation === scopeVersion.current) setRenderNote(null);
        }
      }
    } catch (error) {
      if (operation !== scopeVersion.current) return;
      setExportError(error instanceof Error ? error.message : 'Failed to export playlist interval');
    }
  }

  async function assembleReport() {
    const operation = scopeVersion.current;
    if (!matchId) return;
    try {
      const report = await assembleMatchReport(matchId, generationId);
      if (operation !== scopeVersion.current) return;
      if (generationId && report.generationId !== generationId) throw new Error('Report generation changed; refresh before retrying.');
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
      if (operation !== scopeVersion.current) return;
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
          disabled={Boolean(editingClip)}
          onChange={(event) => setDraft({ key: rangeKey, start: event.target.value, end })}
          className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200"
        />
      </label>
      <label className="block text-xs text-slate-400">
        Clip end
        <input
          value={end}
          disabled={Boolean(editingClip)}
          onChange={(event) => setDraft({ key: rangeKey, start, end: event.target.value })}
          className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200"
        />
      </label>
      <label className="block text-xs text-slate-400">
        Title
        <input value={title} onChange={(event) => setTitle(event.target.value)} className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
      </label>
      <label className="block text-xs text-slate-400">
        Notes
        <input value={notes} onChange={(event) => setNotes(event.target.value)} className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
      </label>
      <button type="button" onClick={() => void addClip()} className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white">
        {editingClip ? 'Save clip changes' : 'Add clip'}
      </button>
      {editingClip && <button type="button" onClick={() => setEditing(null)} className="ml-2 text-xs text-slate-300">Cancel edit</button>}
      {matchId ? (
        <button type="button" onClick={() => void assembleReport()} className="ml-2 px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white">
          Assemble report
        </button>
      ) : null}
      {exportError && <p className="text-xs text-amber-200">{exportError}</p>}
      {reportError && <p className="text-xs text-amber-200">{reportError}</p>}
      {[...storedClips, ...clips.filter((clip) => !generationId || clip.generationId === generationId)].filter((clip, index, all) => all.findIndex((other) => clipKey(other) === clipKey(clip)) === index).map((clip) => (
        <div key={clipKey(clip)}>
        <button
          type="button"
          aria-label={`Open ${clip.start}s to ${clip.end}s`}
          onClick={() => onOpenInterval?.(clip.start)}
          className="block text-left text-xs text-slate-300 hover:text-emerald-300"
        >
          {clip.title ? `${clip.title} · ` : ''}{clip.start}s to {clip.end}s (frame {clip.sourceEndFrameExclusive} exclusive){clip.notes ? ` · ${clip.notes}` : ''}
        </button>
        {clip.evidenceIds?.length ? <p className="text-xs text-slate-400">Evidence: {clip.evidenceIds.join(', ')}</p> : null}
        {clip.correctionId && onClipUpdated && generationId === clip.generationId && (
          <button type="button" aria-label={`Edit clip ${clip.title || `${clip.start}s to ${clip.end}s`}`}
            onClick={() => { setEditing({ matchId, generationId, clip }); setTitle(clip.title ?? ''); setNotes(clip.notes); }}
            className="mr-2 text-xs text-sky-300 underline">Edit title and notes</button>
        )}
        {videoAvailable && matchId && generationId && clip.generationId === generationId && (
          <a className="text-xs text-emerald-300 underline" download
            href={`/api/matches/${encodeURIComponent(matchId)}/edits/clip?${new URLSearchParams({ generationId, start: String(clip.start), end: String(clip.end) })}`}>
            Download rendered clip
          </a>
        )}
        </div>
      ))}
      {reportNote && <p className="text-xs text-slate-300">{reportNote}</p>}
      {editNote && <p className="text-xs text-slate-400">{editNote}</p>}
      {renderNote && <p className="text-xs text-slate-400">{renderNote}</p>}
      <p className="text-xs text-slate-500">Reviewed passages do not establish a whole-match frequency.</p>
    </section>
  );
}
