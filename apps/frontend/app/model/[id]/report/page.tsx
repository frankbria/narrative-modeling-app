'use client';

/**
 * The model report (#795) — one page a user can hand to whoever asked "why this
 * model, and what drives it?".
 *
 * The page's only real job is to preserve provenance. A section the platform never
 * recorded renders as an explicit "Not recorded" with the reason, never as an empty
 * table — an empty leaderboard reads as "nothing else was tried", which is a claim
 * the data does not support (#536).
 */

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { modelService } from '@/lib/services/model';
import type { ModelReport } from '@/lib/types/modelReport';
import {
  BaselineSection,
  CaveatsSection,
  DataSection,
  DriversSection,
  LeaderboardSection,
  ReproducibilitySection,
  WinnerSection,
} from '@/components/model-report/ReportSections';

function useModelReport(modelId: string) {
  const [report, setReport] = useState<ModelReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!modelId) return;
    let cancelled = false;
    modelService
      .getModelReport(modelId)
      .then((data) => {
        if (!cancelled) setReport(data);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load report');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [modelId]);

  return { report, error, loading };
}

/** What the page shows while there is no report: loading, the error, or nothing. */
function ReportStatus(props: { loading: boolean; error: string | null }) {
  const { loading, error } = props;
  if (loading) return <div className="p-8 text-muted-foreground">Loading report…</div>;
  if (error) return <div className="p-8 text-destructive">{error}</div>;
  return null;
}

function ReportHeader(props: { report: ModelReport; onDownload: VoidFunction }) {
  const { report, onDownload } = props;
  const trained = report.trained_at ? new Date(report.trained_at).toLocaleString() : '—';
  return (
    <div className="mb-6 flex items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">
          Model report — {report.model_name}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {report.problem_type} · trained {trained}
        </p>
      </div>
      <div className="flex gap-2 print:hidden">
        <button
          onClick={onDownload}
          className="rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground hover:bg-muted"
        >
          Download Markdown
        </button>
        <button
          onClick={() => window.print()}
          className="rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground hover:bg-muted"
        >
          Print / Save as PDF
        </button>
      </div>
    </div>
  );
}

/** Fetch the report as Markdown and hand it to the browser as a download. */
async function saveMarkdown(modelId: string, modelName: string | undefined) {
  const text = await modelService.getModelReportMarkdown(modelId);
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }));
  const link = document.createElement('a');
  link.href = url;
  // The backend runs the same value through `sanitize_filename` + RFC 5987 for
  // its Content-Disposition; browsers sanitize `download` themselves, but the
  // two paths naming the same file should not disagree about what it is called.
  const base = (modelName ?? modelId)
    .replace(/[/\\:*?"<>|\u0000-\u001f]/g, '_')
    .trim()
    .slice(0, 100);
  link.download = `${base || modelId}-report.md`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function useModelId(): string {
  const params = useParams();
  return String(params?.id ?? '');
}

export default function ModelReportPage() {
  const modelId = useModelId();
  const { report, error, loading } = useModelReport(modelId);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // Not memoized: this is a click handler on a plain button, so `useCallback` buys
  // nothing — and reading `report?.model_name` from a dependency array trips the
  // React Compiler's preserve-manual-memoization rule, which is a blocking error here.
  const downloadMarkdown = async () => {
    // A rejection here (expired session → 401, network drop) was an unhandled
    // promise and the button simply did nothing — the worst outcome for an export
    // someone is about to send to a reviewer, because it looks like it worked.
    setDownloadError(null);
    try {
      await saveMarkdown(modelId, report?.model_name);
    } catch (e: unknown) {
      setDownloadError(
        e instanceof Error ? e.message : 'Could not download the report.'
      );
    }
  };

  if (!report) return <ReportStatus loading={loading} error={error} />;

  return (
    <div className="mx-auto max-w-4xl p-6 print:p-0">
      <ReportHeader report={report} onDownload={downloadMarkdown} />

      {downloadError && (
        <p
          role="alert"
          className="mb-4 rounded-md border border-border bg-muted p-3 text-sm text-destructive print:hidden"
        >
          {downloadError}
        </p>
      )}

      <p className="mb-8 rounded-md border border-border bg-muted p-4 text-sm text-muted-foreground">
        Every figure below is either read from what the training run recorded, or
        computed from stored data and labelled as such. Sections marked{' '}
        <strong className="text-foreground">Not recorded</strong> were never captured —
        that is not the same as zero.
      </p>

      <DataSection report={report} />
      <LeaderboardSection report={report} />
      <BaselineSection report={report} />
      <WinnerSection report={report} />
      <DriversSection report={report} />
      <CaveatsSection report={report} />
      <ReproducibilitySection report={report} />

      <div className="print:hidden">
        <Link href={`/model/${modelId}`} className="text-sm text-muted-foreground underline">
          Back to model
        </Link>
      </div>
    </div>
  );
}
