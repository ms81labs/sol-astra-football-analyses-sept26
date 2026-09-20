/** Monetary fields are projections, not an independent client-side billing ledger. */
export interface CostSummary {
  schemaVersion: number;
  currency: string;
  authorisedBudget: number;
  attemptCount: number;
  settledTotal: number;
  outstandingReserved: number;
  unsettledTotal: number;
  unsettledAttemptCount: number;
  /** Deprecated: outstandingReserved + unsettledTotal, never add unsettledTotal again. */
  reservedTotal: number;
  billingComplete: boolean;
  actualTotal: number | null;
  reasonCodes: string[];
}

const finiteAmount = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0;
const count = (value: unknown) => finiteAmount(value) && Number.isSafeInteger(value) ? value : 0;

/** Legacy/malformed payloads must not acquire final-bill evidence through defaults. */
export function normaliseCostSummary(value: unknown): CostSummary {
  const raw = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  const verified = raw.schemaVersion === 2;
  const settled = finiteAmount(raw.settledTotal) ? raw.settledTotal : 0;
  const outstanding = finiteAmount(raw.outstandingReserved) ? raw.outstandingReserved : 0;
  const unsettled = finiteAmount(raw.unsettledTotal) ? raw.unsettledTotal
    : finiteAmount(raw.reservedTotal) ? raw.reservedTotal : 0;
  const attempts = count(raw.attemptCount);
  const uncertain = count(raw.unsettledAttemptCount);
  const complete = verified && raw.billingComplete === true && attempts > 0
    && finiteAmount(raw.actualTotal) && raw.actualTotal === settled
    && finiteAmount(raw.settledTotal) && raw.outstandingReserved === 0
    && raw.unsettledTotal === 0 && raw.unsettledAttemptCount === 0;
  const reasons = Array.isArray(raw.reasonCodes)
    ? raw.reasonCodes.filter((item): item is string => typeof item === 'string') : [];
  if (!verified || (raw.billingComplete === true && !complete)) reasons.push('BILLING_UNVERIFIED');
  return {
    schemaVersion: 2, currency: typeof raw.currency === 'string' && /^[A-Z]{3}$/.test(raw.currency) ? raw.currency : 'Unknown currency',
    authorisedBudget: finiteAmount(raw.authorisedBudget) ? raw.authorisedBudget : 0,
    attemptCount: attempts, settledTotal: settled, outstandingReserved: outstanding,
    unsettledTotal: unsettled, unsettledAttemptCount: uncertain,
    reservedTotal: outstanding + unsettled, billingComplete: complete,
    actualTotal: complete ? raw.actualTotal as number : null, reasonCodes: [...new Set(reasons)],
  };
}

export function formatMoney(value: number): string {
  // Retain supported sub-cent amounts; a small positive charge must not render as zero.
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 12 });
}
