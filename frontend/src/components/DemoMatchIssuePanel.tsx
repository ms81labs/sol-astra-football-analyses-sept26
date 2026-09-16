import { useMemo, useState } from 'react';

import type { MatchIssue, MatchIssueBucket, MatchIssueEvidenceTarget, ReviewRange } from '../types';

interface DemoMatchIssuePanelProps {
  issues: MatchIssue[];
  currentFrame: number;
  currentTimestamp: number;
  reviewRange: ReviewRange | null;
  processingBackend: 'local' | 'remote' | 'unknown';
  onCreateIssue: (payload: {
    bucket: MatchIssueBucket;
    evidenceTarget: MatchIssueEvidenceTarget;
    processingBackend: 'local' | 'remote' | 'unknown';
    note: string;
  }) => Promise<MatchIssue | null>;
  onSeekToIssue: (issue: MatchIssue) => void;
  onDeleteIssue: (issueId: string) => void;
}

const ISSUE_BUCKET_OPTIONS: Array<{ value: MatchIssueBucket; label: string }> = [
  { value: 'upload_calibration_issue', label: 'Upload / Calibration' },
  { value: 'tracking_failure', label: 'Tracking Failure' },
  { value: 'team_classification_issue', label: 'Team Classification' },
  { value: 'ocr_issue', label: 'OCR Issue' },
  { value: 'event_layer_issue', label: 'Event Layer' },
  { value: 'tactical_summary_issue', label: 'Tactical Summary' },
  { value: 'ui_review_issue', label: 'UI / Review' },
  { value: 'report_export_issue', label: 'Report / Export' },
];

const EVIDENCE_TARGET_OPTIONS: Array<{ value: MatchIssueEvidenceTarget; label: string }> = [
  { value: 'product_bug', label: 'Product bug' },
  { value: 'trust_eval', label: 'Trust eval' },
  { value: 'both', label: 'Both' },
];

function formatIssueTiming(issue: MatchIssue) {
  if (issue.frameStart === issue.frameEnd) {
    return `Frame ${issue.frameStart} @ ${issue.timestampStart.toFixed(1)}s`;
  }
  return `Frames ${issue.frameStart}-${issue.frameEnd} @ ${issue.timestampStart.toFixed(1)}-${issue.timestampEnd.toFixed(1)}s`;
}

export default function DemoMatchIssuePanel({
  issues,
  currentFrame,
  currentTimestamp,
  reviewRange,
  processingBackend,
  onCreateIssue,
  onSeekToIssue,
  onDeleteIssue,
}: DemoMatchIssuePanelProps) {
  const [bucket, setBucket] = useState<MatchIssueBucket>('tracking_failure');
  const [evidenceTarget, setEvidenceTarget] = useState<MatchIssueEvidenceTarget>('product_bug');
  const [note, setNote] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const captureSummary = useMemo(() => {
    if (!reviewRange) {
      return `Capturing current frame ${currentFrame} @ ${currentTimestamp.toFixed(1)}s`;
    }
    return `Capturing selected range ${reviewRange.startFrame}-${reviewRange.endFrame}`;
  }, [currentFrame, currentTimestamp, reviewRange]);

  return (
    <section className="rounded-lg border border-amber-400/30 bg-slate-900 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-amber-200">Demo Match Issues</h3>
          <p className="mt-1 text-xs text-slate-400">
            Log review failures with a bucket, captured range, backend mode, and evidence target.
          </p>
        </div>
        <div className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-[11px] text-slate-400">
          <div>{captureSummary}</div>
          <div className="mt-1">Backend: {processingBackend}</div>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <label className="text-xs text-slate-400">
          Failure bucket
          <select
            value={bucket}
            onChange={(event) => setBucket(event.target.value as MatchIssueBucket)}
            disabled={isSaving}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100"
          >
            {ISSUE_BUCKET_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-400">
          Evidence target
          <select
            value={evidenceTarget}
            onChange={(event) => setEvidenceTarget(event.target.value as MatchIssueEvidenceTarget)}
            disabled={isSaving}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100"
          >
            {EVIDENCE_TARGET_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="mt-3 block text-xs text-slate-400">
        What went wrong
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          disabled={isSaving}
          placeholder="Describe the visible failure and why it matters."
          className="mt-1 min-h-24 w-full rounded border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500"
        />
      </label>

      <div className="mt-3 flex items-center justify-between gap-3">
        <p className="text-[11px] text-slate-500">Use the current frame or an active review range as the captured evidence window.</p>
        <button
          type="button"
          onClick={async () => {
            if (isSaving) return;
            const trimmed = note.trim();
            if (!trimmed) return;
            setIsSaving(true);
            try {
              const created = await onCreateIssue({
                bucket,
                evidenceTarget,
                processingBackend,
                note: trimmed,
              });
              if (created) setNote('');
            } catch {
              // The caller owns error reporting; keep the unsaved text here.
            } finally {
              setIsSaving(false);
            }
          }}
          disabled={isSaving}
          className="rounded border border-amber-400/40 bg-amber-500/15 px-3 py-2 text-sm font-semibold text-amber-200 transition-colors hover:bg-amber-500/25"
        >
          Log Issue
        </button>
      </div>

      <div className="mt-4 space-y-2">
        {issues.length === 0 ? (
          <p className="rounded border border-dashed border-slate-700 px-3 py-3 text-xs text-slate-500">
            No demo-match issues logged yet.
          </p>
        ) : (
          issues.map((issue) => (
            <div key={issue.id} className="rounded border border-slate-700 bg-slate-950 px-3 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-amber-200">
                    {ISSUE_BUCKET_OPTIONS.find((option) => option.value === issue.bucket)?.label ?? issue.bucket}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">{formatIssueTiming(issue)}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Backend: {issue.processingBackend} · Evidence: {issue.evidenceTarget}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => onSeekToIssue(issue)}
                    className="rounded border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-200 hover:bg-slate-700"
                  >
                    Review
                  </button>
                  <button
                    type="button"
                    onClick={() => onDeleteIssue(issue.id)}
                    className="rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-400 hover:bg-slate-800"
                  >
                    Delete
                  </button>
                </div>
              </div>
              <p className="mt-2 text-sm text-slate-200">{issue.note}</p>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
