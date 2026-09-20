/** HTTP and snapshot errors preserve the server's machine-readable disposition. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(message: string, status: number, code: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.name = 'ApiError';
  }
}

function errorFields(value: unknown): { message?: string; code?: string } {
  if (typeof value === 'string') return { message: value, ...(/^[A-Z][A-Z0-9_]+$/.test(value) ? { code: value } : {}) };
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const record = value as Record<string, unknown>;
  const nested = errorFields(record.detail ?? record.error);
  return {
    message: typeof record.message === 'string' ? record.message : nested.message,
    code: typeof record.code === 'string' ? record.code : nested.code,
  };
}

export async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let fields: ReturnType<typeof errorFields> = {};
    try { fields = errorFields(await response.json()); } catch { /* Preserve HTTP status for a non-JSON error. */ }
    throw new ApiError(fields.message ?? `Request failed with status ${response.status}`,
      response.status, fields.code ?? `HTTP_${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function generationUrl(path: string, generationId?: string | null): string {
  if (!generationId) return path;
  return `${path}${path.includes('?') ? '&' : '?'}generationId=${encodeURIComponent(generationId)}`;
}

export function assertGeneration(payload: { generationId?: string | null }, expected?: string | null): void {
  if (expected && payload.generationId !== expected) {
    throw new ApiError('Snapshot changed or its provenance is missing. Refresh before editing.',
      409, 'GENERATION_RESPONSE_MISMATCH');
  }
}

export async function readGeneration<T extends object>(path: string, generationId?: string | null, signal?: AbortSignal): Promise<T & { generationId?: string | null }> {
  const payload = await parseJson<T & { generationId?: string | null }>(
    await fetch(generationUrl(path, generationId), { signal }));
  assertGeneration(payload, generationId);
  return payload;
}
