export interface CapabilityEntry {
  id: string;
  label: string;
  status: string;
  evidenceClass: string;
  evidenceLink: string;
  notes: string;
  independentlyVisible: boolean;
}

export interface WorkbenchDossier {
  baseline: {
    selectedCommit: string;
    declaredCameraProfile: string;
    declaredWorkflow: string;
    unresolvedGates: string[];
    permittedNextActions: string[];
    forbiddenActions: string[];
    capabilities: CapabilityEntry[];
    evidenceClasses: Record<string, string>;
  };
  release: {
    deploymentBoundary: string;
    gNetworkRequiredForNonLocal: boolean;
    nativeCode: string;
  };
  evaluation: {
    accepted: boolean;
    completeTasks: number;
    requiredTasks: number;
    reasonCodes: string[];
  };
  gpu: {
    available: boolean;
    canPromoteDefault: boolean;
    reasonCodes: string[];
  };
  native: {
    approved: boolean;
    reasonCodes: string[];
  };
}

export interface MetricAvailability {
  metric: string;
  definitionVersion: string;
  value: number | null;
  availability: string;
  reasonCodes: string[];
  unit?: string | null;
}

export async function fetchWorkbenchDossier(): Promise<WorkbenchDossier> {
  const response = await fetch('/api/workbench/dossier');
  if (!response.ok) {
    throw new Error(`Failed to load workbench dossier: ${response.status}`);
  }
  return response.json() as Promise<WorkbenchDossier>;
}

export async function searchWorkbenchEvents(query: string, matchId: string, events: Array<Record<string, unknown>>) {
  const response = await fetch('/api/workbench/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, matchId, events }),
  });
  if (!response.ok) {
    throw new Error(`Failed to run typed search: ${response.status}`);
  }
  return response.json() as Promise<{
    query: { unanswerable: boolean; reason: string | null; eventFamily: string };
    results: Array<{ eventId: string; timestamp: number; evidenceIds: string[] }>;
  }>;
}

export async function fetchPendingCorrections(matchId: string) {
  const response = await fetch(`/api/workbench/matches/${matchId}/corrections?state=pending`);
  if (!response.ok) {
    throw new Error(`Failed to load pending corrections: ${response.status}`);
  }
  return response.json() as Promise<{ items: Array<{ correctionId: string; kind: string; saveState: string }> }>;
}

export async function recoverMatchCorrection(matchId: string, correctionId: string) {
  const response = await fetch(`/api/workbench/matches/${matchId}/corrections/${correctionId}/recover`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Failed to recover correction: ${response.status}`);
  }
  return response.json() as Promise<{ correctionId: string; saveState: string }>;
}

export async function undoMatchCorrection(matchId: string, correctionId: string) {
  const response = await fetch(`/api/workbench/matches/${matchId}/corrections/${correctionId}/undo`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Failed to undo correction: ${response.status}`);
  }
  return response.json() as Promise<{ correctionId: string; undoOf: string }>;
}

export async function exportPlaylistInterval(timestampStart: number, timestampEnd: number, sourceFps: number) {
  const response = await fetch('/api/workbench/playlists/export-interval', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ timestampStart, timestampEnd, sourceFps }),
  });
  if (!response.ok) {
    throw new Error(`Failed to export playlist interval: ${response.status}`);
  }
  return response.json() as Promise<{ sourceStartSeconds: number; sourceEndSeconds: number; sourceEndFrameExclusive: number }>;
}
