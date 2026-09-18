# Job ledger budget and recovery

SQLite is the authority for job requests, attempts, charges, cancellation, and leases. Every process must open the `Storage` database; do not keep a separate in-memory queue or create a second ledger file.

## Admission and retry

- Submit with `admit(..., mode="submit")`. Repeating the same request returns its existing attempt and creates no charge. A changed payload under the same request ID is rejected.
- Retry only through `POST /api/jobs/{id}/retry`, which uses `admit(..., mode="retry")`. Ordinary submission never retries a terminal job.
- An `outcome_unknown` attempt must be reconciled against the provider before retry. Never infer failure from a timeout or process restart.
- A request has at most three attempts.

## Leases and recovery

Workers own attempts with `owner_id="job:<job-id>"` and renew the 60-second lease on processing progress. Compare-and-swap revisions reject stale writers; a different owner cannot mutate an unexpired lease.

Workers also renew leases on an independent 20-second loop, so a quiet decoder or provider poll does not look abandoned. Cancellation is cooperative: workers check the durable cancel flag at startup and progress/poll boundaries, confirm provider termination, then record cleanup success or failure separately.

Application startup calls `reclaim_expired(now=...)`. It changes only expired active attempts to `outcome_unknown` and logs the count. Opening a ledger never performs recovery. Reconcile an unknown attempt with `reconcile_attempt` after checking the provider outcome and cost.

## Budget invariant

Admission reserves at most the authorised remainder:

`settled + outstanding reserved + unsettled <= authorised budget`

Terminal completion, failure, or confirmed cancellation settles actual cost and releases the unused reservation. An unknown outcome converts its reservation to unsettled cost until reconciliation. Cancellation never erases settled charges.

Daytona admission requires a positive authorised budget. Because the provider adapter does not return a trustworthy final charge, Daytona completion, failure, and cancellation retain the reservation as unsettled and require operator reconciliation; they never assume a zero cost.

The job receipt exposes `attemptCount`, `reservedTotal`, `settledTotal`, `unsettledTotal`, and `actualTotal`. `actualTotal` is `null` while any cost remains unsettled.
