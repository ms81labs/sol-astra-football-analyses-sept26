import { useState } from 'react';

import { fetchJobBudget, fetchJobCharges, fetchJobCost, fetchJobRates, fetchJobView, postJobCancel, postJobLostConnection, postJobTimeout, postMatchJob } from '../utils/workbench';

interface MatchJobWritePanelProps {
  matchId?: string;
}

export default function MatchJobWritePanel({ matchId }: MatchJobWritePanelProps) {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

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
          try {
            const view = await fetchJobView(payload.jobId);
            if (view.cancelRequested === false) {
              next += ' Stored job view keeps cancelRequested false. A queued durable job is not completed work.';
            }
          } catch {
            // Keep the posted-job note if the job view is unavailable.
          }
          try {
            const rates = await fetchJobRates(payload.jobId);
            if (rates.exportFpsEqualsInferenceFps === false) {
              next += ' Stored job rates keep exportFpsEqualsInferenceFps false. Job sampling rates are not leftover four-rate POST.';
            }
          } catch {
            // Keep the posted-job note if the job rates are unavailable.
          }
          setJobId(payload.jobId);
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

  async function requestTimeout() {
    if (!jobId || pending) return;
    setPending(true);
    try {
      const timedOut = await postJobTimeout(jobId);
      if (
        timedOut.durablePhase === 'outcome_unknown'
        && timedOut.status !== 'cancelled'
        && timedOut.cleanupResult === 'unknown'
      ) {
        setNote('Posted job timeout keeps durablePhase outcome_unknown. Timeout is not cancelled. cleanupResult stays unknown.');
      }
    } catch {
      // Keep the posted-job note if timeout is refused.
    } finally {
      setPending(false);
    }
  }

  async function requestLostConnection() {
    if (!jobId || pending) return;
    setPending(true);
    try {
      const disconnected = await postJobLostConnection(jobId);
      if (
        disconnected.durablePhase === 'outcome_unknown'
        && disconnected.status !== 'cancelled'
      ) {
        setNote('Posted lost connection keeps durablePhase outcome_unknown. A dropped connection is not completed work. status is not cancelled.');
      }
    } catch {
      // Keep the posted-job note if lost-connection is refused.
    } finally {
      setPending(false);
    }
  }

  async function requestCancel() {
    if (!jobId || pending) return;
    setPending(true);
    try {
      const cancelled = await postJobCancel(jobId);
      if (cancelled.cancelRequested === true) {
        setNote('Posted job cancel keeps cancelRequested true. Client completeMatch is not sent. A cancel flag is not completed work. Stored job rates keep exportFpsEqualsInferenceFps false. Job sampling rates are not leftover four-rate POST.');
      }
    } catch {
      // Keep the posted-job note if cancel is refused.
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
      {jobId && (
        <>
          <button
            type="button"
            aria-label="Cancel durable job"
            onClick={() => void requestCancel()}
            disabled={pending}
            className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
          >
            Cancel durable job
          </button>
          <button
            type="button"
            aria-label="Timeout durable job"
            onClick={() => void requestTimeout()}
            disabled={pending}
            className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
          >
            Timeout durable job
          </button>
          <button
            type="button"
            aria-label="Mark lost connection"
            onClick={() => void requestLostConnection()}
            disabled={pending}
            className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
          >
            Mark lost connection
          </button>
        </>
      )}
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
