import type { DrillResponse, TacticalReport } from '../types';
import { ApiError } from './request';

export interface ReportRecord {
  matchId: string;
  generationId: string;
  status: 'current' | 'historical';
  reportId: string;
  validationDisposition: string;
  payload: TacticalReport | DrillResponse;
}
export interface ReportView {
  matchId: string;
  generationId: string;
  status: 'current' | 'historical';
  reports: Partial<Record<'tactical_report' | 'drills', ReportRecord>>;
  notices: Array<{ code: string }>;
}

export function requireReportScope(value: unknown, matchId: string, generationId: string): TacticalReport & DrillResponse {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new ApiError('Report response is unavailable.', 409, 'REPORT_UNCONFIRMED');
  }
  const report = value as TacticalReport & DrillResponse;
  if (report.matchId !== matchId || report.generationId !== generationId
    || !['current', 'historical'].includes(report.status ?? '')
    || !['grounded', 'referenced', 'interpretive', 'deterministic'].includes(report.grounding ?? '')) {
    throw new ApiError('Report belongs to another snapshot or lacks validated provenance. Refresh before retrying.',
      409, 'REPORT_GENERATION_MISMATCH');
  }
  return report;
}

export function reportNotice(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    return 'Report evidence or policy changed. Refresh before explicitly retrying; no provider retry was sent automatically.';
  }
  return 'Report unavailable for this generation. Older reports are retained as historical.';
}
