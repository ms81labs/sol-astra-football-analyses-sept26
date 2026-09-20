import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import OperationsView from './OperationsView';

afterEach(cleanup);
it('does not invent a final zero for a job without billing evidence', () => {
  render(<OperationsView phase="running" />);
  expect(screen.queryByText(/^Actual 0$/)).toBeNull();
  expect(screen.getByText(/Final cost unknown/i)).toBeTruthy();
});

const mixed = { schemaVersion: 2, currency: 'USD', authorisedBudget: 1, attemptCount: 2,
  settledTotal: 0.2, outstandingReserved: 0, unsettledTotal: 0.8, unsettledAttemptCount: 1,
  reservedTotal: 0.8, billingComplete: false, actualTotal: null,
  reasonCodes: ['PROVIDER_OUTCOME_UNKNOWN'] };

it('shows confirmed subtotal and unsettled exposure without calling either the final bill', () => {
  render(<OperationsView cost={mixed} />);
  expect(screen.getByText(/Confirmed subtotal USD 0.20/)).toBeTruthy();
  expect(screen.getByText(/Unsettled exposure USD 0.80/)).toBeTruthy();
  expect(screen.getByText(/Final cost unknown/)).toBeTruthy();
});

it('displays genuine confirmed zero and its currency', () => {
  render(<OperationsView cost={{...mixed, currency:'EUR', settledTotal:0, unsettledTotal:0,
    unsettledAttemptCount:0, reservedTotal:0, actualTotal:0, billingComplete:true,
    reasonCodes:['LOCAL_NON_BILLABLE']}} />);
  expect(screen.getByText(/Final cost EUR 0.00/)).toBeTruthy();
  expect(screen.queryByText(/Final cost unknown/)).toBeNull();
});

it('refuses a contradictory finality claim from an older or malformed consumer', () => {
  render(<OperationsView cost={{...mixed, actualTotal:0}} />);
  expect(screen.queryByText(/Final cost USD 0.00/)).toBeNull();
  expect(screen.getByText(/Final cost unknown/)).toBeTruthy();
});
