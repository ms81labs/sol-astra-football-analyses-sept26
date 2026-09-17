import { useState } from 'react';

import { fetchLeftoverCacheTenancy } from '../utils/workbench';

export default function LeftoverCacheTenancyPanel() {
  const [note, setNote] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function requestCacheTenancy() {
    if (pending) return;
    setPending(true);
    try {
      const payload = await fetchLeftoverCacheTenancy();
      if (payload.crossTenant?.allowed === false && payload.columnar?.enabled === false) {
        setNote('Requested leftover cache tenancy keeps crossTenant allowed false. CROSS_TENANT_CACHE_BLOCKED stays blocking. Leftover DuckDB stays unadmitted.');
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
    <section aria-label="Unforced leftover cache tenancy" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Unforced leftover cache tenancy</h4>
      <button
        type="button"
        aria-label="Request leftover cache tenancy"
        onClick={() => void requestCacheTenancy()}
        disabled={pending}
        className="px-3 py-1.5 rounded bg-slate-700 text-xs font-semibold text-white disabled:opacity-50"
      >
        Request leftover cache tenancy
      </button>
      {note && <p className="text-xs text-slate-400">{note}</p>}
    </section>
  );
}
