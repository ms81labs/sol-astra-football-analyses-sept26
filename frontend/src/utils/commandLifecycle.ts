import { ApiError } from './request';

/** Save-state describes durability, not whether the analytical effect was published. */
export interface CommandReceipt {
  correctionId: string;
  commandId?: string;
  kind?: string;
  saveState: string;
  applyState?: 'received' | 'committed' | 'applying' | 'applied' | 'failed';
  appliedGeneration?: string | null;
  baseGeneration?: string | null;
  version?: number;
  undoOf?: string | null;
  author?: string;
  payload?: Record<string, unknown> | null;
  lastError?: string | null;
}

export interface CommandControls {
  baseGeneration?: string;
  expectedVersion?: number;
  commandId?: string;
  idempotencyKey?: string;
}

export type CommandState = 'recorded' | 'applying' | 'applied' | 'failed' | 'conflicted' | 'unavailable';

export function commandState(receipt: CommandReceipt): CommandState {
  if (receipt.saveState === 'conflicted') return 'conflicted';
  if (receipt.applyState === 'failed') return 'failed';
  if (receipt.applyState === 'applied') return receipt.appliedGeneration ? 'applied' : 'unavailable';
  if (receipt.applyState === 'applying') return 'applying';
  return 'recorded';
}

export const COMMAND_LABEL: Record<CommandState, string> = {
  recorded: 'Edit recorded — application not confirmed',
  applying: 'Applying edit',
  applied: 'Edit applied',
  failed: 'Edit failed — previous generation retained',
  conflicted: 'Stale correction — refresh before retrying',
  unavailable: 'Application unconfirmed — refresh required',
};

export function commandErrorState(error: unknown): CommandState {
  return error instanceof ApiError && error.status === 409 ? 'conflicted' : 'unavailable';
}

export function canUndo(item: CommandReceipt, history: readonly CommandReceipt[]): boolean {
  return item.kind !== 'undo' && !item.undoOf && commandState(item) === 'applied'
    && !history.some((other) => other.undoOf === item.correctionId && commandState(other) === 'applied');
}

export function mergeReceipt(history: readonly CommandReceipt[], receipt: CommandReceipt): CommandReceipt[] {
  const index = history.findIndex((item) => item.correctionId === receipt.correctionId);
  if (index < 0) return [...history, receipt];
  const previous = history[index];
  // A delayed pending/log response cannot undo a confirmed publication receipt.
  if (commandState(previous) === 'applied' && commandState(receipt) !== 'applied') return [...history];
  if ((previous.version ?? 0) > (receipt.version ?? 0)) return [...history];
  return history.map((item, offset) => offset === index ? { ...item, ...receipt } : item);
}

/** No automatic retry: an ambiguous transport outcome retains the same ID for explicit recovery. */
export function newCommandControls(baseGeneration?: string | null, expectedVersion?: number): CommandControls {
  if (!baseGeneration) throw new ApiError('No committed snapshot is selected. Refresh before editing.', 409, 'GENERATION_REQUIRED');
  return { baseGeneration, ...(expectedVersion != null ? { expectedVersion } : {}), commandId: crypto.randomUUID() };
}

/** Exact nextafter(+infinity) for a finite JS float; matches the server's half-open coverage bound. */
export function nextTimestamp(value: number): number {
  if (!Number.isFinite(value)) throw new Error('Observation timestamp must be finite.');
  if (Object.is(value, -0) || value === 0) return Number.MIN_VALUE;
  const view = new DataView(new ArrayBuffer(8));
  view.setFloat64(0, value, false);
  const bits = view.getBigUint64(0, false);
  view.setBigUint64(0, value > 0 ? bits + 1n : bits - 1n, false);
  return view.getFloat64(0, false);
}
