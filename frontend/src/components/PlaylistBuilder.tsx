import { useState } from 'react';

interface PlaylistClip {
  start: number;
  end: number;
  notes: string;
}

export default function PlaylistBuilder() {
  const [start, setStart] = useState('12');
  const [end, setEnd] = useState('14');
  const [notes, setNotes] = useState('');
  const [clips, setClips] = useState<PlaylistClip[]>([]);

  function addClip() {
    const from = Number(start);
    const to = Number(end);
    if (!Number.isFinite(from) || !Number.isFinite(to)) return;
    setClips((current) => [...current, { start: from, end: to, notes }]);
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
      <button type="button" onClick={addClip} className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white">
        Add clip
      </button>
      {clips.map((clip) => (
        <p key={`${clip.start}-${clip.end}-${clip.notes}`} className="text-xs text-slate-300">
          {clip.start}s to {clip.end}s{clip.notes ? ` · ${clip.notes}` : ''}
        </p>
      ))}
      <p className="text-xs text-slate-500">Reviewed passages do not establish a whole-match frequency.</p>
    </section>
  );
}
