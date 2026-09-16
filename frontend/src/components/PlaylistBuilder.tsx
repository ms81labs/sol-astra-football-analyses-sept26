import { useState } from 'react';

import { assembleMatchReport, exportPlaylistInterval } from '../utils/workbench';

interface PlaylistClip {
  start: number;
  end: number;
  notes: string;
  sourceEndFrameExclusive: number;
}

interface PlaylistBuilderProps {
  matchId?: string;
}

export default function PlaylistBuilder({ matchId }: PlaylistBuilderProps) {
  const [start, setStart] = useState('12');
  const [end, setEnd] = useState('14');
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
      const interval = await exportPlaylistInterval(from, to, 25);
      setExportError(null);
      setClips((current) => [...current, {
        start: interval.sourceStartSeconds,
        end: interval.sourceEndSeconds,
        notes,
        sourceEndFrameExclusive: interval.sourceEndFrameExclusive,
      }]);
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
        <input value={start} onChange={(event) => setStart(event.target.value)} className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
      </label>
      <label className="block text-xs text-slate-400">
        Clip end
        <input value={end} onChange={(event) => setEnd(event.target.value)} className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-slate-200" />
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
      {clips.map((clip) => (
        <p key={`${clip.start}-${clip.end}-${clip.sourceEndFrameExclusive}-${clip.notes}`} className="text-xs text-slate-300">
          {clip.start}s to {clip.end}s (frame {clip.sourceEndFrameExclusive} exclusive){clip.notes ? ` · ${clip.notes}` : ''}
        </p>
      ))}
      {reportNote && <p className="text-xs text-slate-300">{reportNote}</p>}
      <p className="text-xs text-slate-500">Reviewed passages do not establish a whole-match frequency.</p>
    </section>
  );
}
