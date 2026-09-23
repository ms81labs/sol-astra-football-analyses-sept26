import { useEffect, useLayoutEffect, useRef, useState } from 'react';

import { fetchMatchExport, fetchMatchPackage, type MatchExportBundle } from '../utils/workbench';

interface MatchPackagePanelProps {
  matchId?: string;
  generationId?: string;
  onReopen?: (matchId: string, generationId: string) => Promise<boolean | void>;
}

export default function MatchPackagePanel({ matchId, generationId, onReopen }: MatchPackagePanelProps) {
  const scopeVersion = useRef(0);
  useLayoutEffect(() => { scopeVersion.current += 1; return () => { scopeVersion.current += 1; }; }, [matchId, generationId]);
  const [note, setNote] = useState<string | null>(null);
  const [reopenStatus, setReopenStatus] = useState<string | null>(null);

  async function reopen(file?: File) {
    if (!file || !onReopen) return;
    const operation = scopeVersion.current;
    try {
      // ponytail: 256 MiB in-memory JSON ceiling; stream a versioned archive if whole-match packages exceed it.
      if (file.size > 256 * 1024 * 1024) throw new Error('Package exceeds the local reopen limit.');
      const imported = JSON.parse(await file.text()) as Partial<MatchExportBundle>;
      if (operation !== scopeVersion.current) return;
      if (imported.schemaVersion !== 'match_bundle_v1' || typeof imported.matchId !== 'string'
          || !/^[a-f0-9]{32}$/.test(imported.matchId)
          || typeof imported.generationId !== 'string' || !imported.generationId || !imported.playlist?.sourceSha256
          || !Array.isArray(imported.corrections) || !Array.isArray(imported.annotations)) {
        throw new Error('Invalid editable match package.');
      }
      const retained = await fetchMatchExport(imported.matchId);
      if (operation !== scopeVersion.current) return;
      if (retained.schemaVersion !== imported.schemaVersion || retained.generationId !== imported.generationId
          || retained.playlist?.sourceSha256 !== imported.playlist.sourceSha256) {
        throw new Error('Source or generation changed; this package cannot be reopened for editing.');
      }
      if (JSON.stringify(retained.playlist) !== JSON.stringify(imported.playlist)
          || JSON.stringify(retained.corrections) !== JSON.stringify(imported.corrections)
          || JSON.stringify(retained.annotations) !== JSON.stringify(imported.annotations)) {
        throw new Error('Package contents differ from retained state; import would lose those edits.');
      }
      if (await onReopen(imported.matchId, imported.generationId) === false) throw new Error('Could not reopen the retained match.');
      if (operation === scopeVersion.current) setReopenStatus('Editable package reopened from retained source.');
    } catch (error) {
      if (operation === scopeVersion.current) setReopenStatus(error instanceof Error ? error.message : 'Could not reopen package.');
    }
  }

  useEffect(() => {
    if (!matchId) return;
    let cancelled = false;
    fetchMatchPackage(matchId)
      .then((payload) => {
        if (cancelled) return;
        const limitations = payload.analyst?.limitations ?? [];
        const schema = payload.operator?.manifest?.schema;
        const labelsIncomplete = limitations.some((item) => /independent labels 0\/18/i.test(item));
        if (labelsIncomplete && schema === 'match_package_v1' && payload.operator?.secretsAdmitted === true) {
          setNote('Coverage and limitations summary: Independent labels 0/18 complete. Versioned report match_package_v1. This package does not expose credentials.');
        } else {
          setNote(null);
        }
      })
      .catch(() => {
        if (!cancelled) setNote(null);
      });
    return () => {
      cancelled = true;
    };
  }, [matchId]);

  if (!matchId) return null;
  return (
    <section aria-label="Match package" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Reviewed match package</h4>
      {note && <p className="text-xs text-slate-400">{note}</p>}
      {generationId && <a className="text-xs text-emerald-300 underline" download={`${matchId}-match.json`}
        href={`/api/matches/${encodeURIComponent(matchId)}/export/match.json?generationId=${encodeURIComponent(generationId)}`}>
        Download editable package
      </a>}
      {onReopen && <label className="block text-xs text-slate-300">Reopen editable package
        <input type="file" accept="application/json,.json" onChange={(event) => { void reopen(event.target.files?.[0]); }} />
      </label>}
      {reopenStatus && <p role="status" className="text-xs text-slate-300">{reopenStatus}</p>}
    </section>
  );
}
