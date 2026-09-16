export default function SecurityBoundary() {
  return (
    <section aria-label="Security boundary" className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs text-slate-300 space-y-1">
      <h3 className="text-[11px] uppercase tracking-wide text-slate-500">Security boundary</h3>
      <p>Model output is untrusted. Only allowlisted actions and known evidence references are admitted.</p>
      <p>No secrets in artifacts, logs, prompts or sandbox payloads.</p>
      <p>Signed and scoped job access is required before a hosted worker can read results.</p>
    </section>
  );
}
