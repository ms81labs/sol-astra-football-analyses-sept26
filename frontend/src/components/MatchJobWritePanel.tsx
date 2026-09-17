import { useState } from 'react';

import { fetchJobBudget, fetchJobCharges, fetchJobCost, postMatchJob } from '../utils/workbench';

interface MatchJobWritePanelProps {
  matchId?: string;
}

export default function MatchJobWritePanel({ matchId }: MatchJobWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (!matchId) return null;

  async function requestJob() {
    if (!matchId || pending) return;
    setPending(true);
    try {
      const payload = await postMatchJob(matchId);
      if (payload.status === 'queued' && payload.reused === false) {
        let next = 'Posted job ignores client GPU and completeMatch. Client secrets are not sent. This is not sealed inference.';
        if (payload.jobId) {
          try {
            const cost = await fetchJobCost(payload.jobId);
            if (typeof cost.reservedTotal === 'number') {
              next += ' Stored job cost reservedTotal is not current-source sealed inference.';
            }
          } catch {
            // Keep the posted-job note if the cost ledger is unavailable.
          }
          try {
            const budget = await fetchJobBudget(payload.jobId);
            if (budget.reserve?.authorised === false) {
              next += ' Stored job budget reserve stays unauthorised. Authorised spend is not invented.';
            }
          } catch {
            // Keep the posted-job note if the budget reserve is unavailable.
          }
          try {
            const charges = await fetchJobCharges(payload.jobId);
            if (charges.chargesErased === false) {
              next += ' Stored job charges stay unerased. Cancellation does not erase incurred charges.';
            }
          } catch {
            // Keep the posted-job note if the charge ledger is unavailable.
          }
        }
        setNote(next);
      } else {
        setNote(null);
      }
    } catch {
      setNote(null);
    } finally {
      setPending(false);
    }
  }

  return (
    <section aria-label="Unforced job write" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced job write</h4>
      <button
        type="button"
        aria-label="Request durable job"
        onClick={() => void requestJob()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request durable job
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
