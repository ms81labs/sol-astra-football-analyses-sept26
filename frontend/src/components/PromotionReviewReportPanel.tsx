import { useEffect, useState } from 'react';

import { fetchPromotionReviewReport } from '../utils/workbench';

export default function PromotionReviewReportPanel() {
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchPromotionReviewReport()
      .then((payload) => {
        if (cancelled) return;
        if (payload.schemaVersion === 'video_to_analysis_promotion_review_report_view_model_v1') {
          setNote('Stored promotion-review report is historical. Historical promotion-review is not current-source promotion. Independent labels stay unreviewed.');
        } else {
          setNote(null);
        }
      })
      .catch(() => {
        if (!cancelled) setNote(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!note) return null;
  return (
    <section aria-label="Stored promotion-review report" className="rounded-lg border border-slate-700 p-3 space-y-2">
      <h4 className="text-xs uppercase tracking-wide text-slate-500">Stored promotion-review report</h4>
      <p className="text-xs text-slate-400">{note}</p>
    </section>
  );
}
