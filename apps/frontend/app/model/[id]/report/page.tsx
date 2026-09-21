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

import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { modelService } from '@/lib/services/model';
import type { ModelReport, ReportSection } from '@/lib/types/modelReport';

function Absent({ section }: { section: ReportSection }) {
  return (
    <div className="rounded-md border border-border bg-muted p-4">
      <p className="text-sm font-medium text-foreground">Not recorded</p>
      {section.note && (
        <p className="mt-1 text-sm text-muted-foreground">{section.note}</p>
      )}
    </div>
  );
}

function num(value: number | null | undefined, digits = 4): string {
  return value === null || value === undefined ? '—' : value.toFixed(digits);
}

export default function ModelReportPage() {
  const params = useParams();
  const modelId = String(params?.id ?? '');
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

  const downloadMarkdown = useCallback(async () => {
    const text = await modelService.getModelReportMarkdown(modelId);
    const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `${report?.model_name ?? modelId}-report.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }, [modelId, report?.model_name]);

  if (loading) return <div className="p-8 text-muted-foreground">Loading report…</div>;
  if (error) return <div className="p-8 text-destructive">{error}</div>;
  if (!report) return null;

  return (
    <div className="mx-auto max-w-4xl p-6 print:p-0">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">
            Model report — {report.model_name}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {report.problem_type} · trained{' '}
            {report.trained_at ? new Date(report.trained_at).toLocaleString() : '—'}
          </p>
        </div>
        <div className="flex gap-2 print:hidden">
          <button
            onClick={downloadMarkdown}
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

      <p className="mb-8 rounded-md border border-border bg-muted p-4 text-sm text-muted-foreground">
        Every figure below is either read from what the training run recorded, or
        computed from stored data and labelled as such. Sections marked{' '}
        <strong className="text-foreground">Not recorded</strong> were never captured —
        that is not the same as zero.
      </p>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold text-foreground">The data</h2>
        <dl className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <dt className="text-muted-foreground">Target</dt>
            <dd className="text-foreground">{report.dataset.target_column}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Training rows</dt>
            <dd className="text-foreground">{report.dataset.n_samples_train ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Features</dt>
            <dd className="text-foreground">{report.dataset.n_features ?? '—'}</dd>
          </div>
        </dl>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold text-foreground">Algorithms tried</h2>
        {report.leaderboard.rows.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="py-2">Algorithm</th>
                <th className="py-2">CV score</th>
                <th className="py-2">Test score</th>
              </tr>
            </thead>
            <tbody>
              {report.leaderboard.rows.map((row) => (
                <tr key={row.algorithm} className="border-b border-border">
                  <td className="py-2 text-foreground">
                    {row.algorithm}
                    {row.is_winner && (
                      <span className="ml-2 text-xs font-medium text-muted-foreground">
                        winner
                      </span>
                    )}
                  </td>
                  <td className="py-2 text-foreground">{num(row.cv_score)}</td>
                  <td className="py-2 text-foreground">{num(row.test_score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Absent section={report.leaderboard} />
        )}
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold text-foreground">Baseline</h2>
        {report.baseline.score !== null ? (
          <p className="text-sm text-foreground">
            A no-skill <strong>{report.baseline.strategy}</strong> predictor scores{' '}
            <strong>{num(report.baseline.score)}</strong> ({report.baseline.metric}) on
            the same held-out rows.
            <span className="mt-1 block text-muted-foreground">{report.baseline.note}</span>
          </p>
        ) : (
          <Absent section={report.baseline} />
        )}
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold text-foreground">Why this model</h2>
        <p className="text-sm text-foreground">
          <strong>{report.winner.algorithm}</strong> — CV {num(report.winner.cv_score)},
          test {num(report.winner.test_score)}.
        </p>
        {report.winner.explanation ? (
          <p className="mt-2 text-sm text-muted-foreground">{report.winner.explanation}</p>
        ) : (
          <div className="mt-2">
            <Absent section={report.winner} />
          </div>
        )}
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold text-foreground">What drives it</h2>
        {report.drivers.features.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {report.drivers.features.map(([name, value]) => (
              <li key={name} className="flex justify-between border-b border-border py-1">
                <span className="text-foreground">{name}</span>
                <span className="text-muted-foreground">{num(value)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <Absent section={report.drivers} />
        )}
      </section>

      {report.caveats.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-lg font-semibold text-foreground">Caveats</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {report.caveats.map((caveat) => (
              <li key={caveat}>{caveat}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold text-foreground">Reproducibility</h2>
        {Object.keys(report.reproducibility.environment).length > 0 ? (
          <ul className="space-y-1 text-sm">
            {Object.entries(report.reproducibility.environment).map(([k, v]) => (
              <li key={k} className="flex justify-between border-b border-border py-1">
                <span className="text-foreground">{k}</span>
                <span className="text-muted-foreground">{v}</span>
              </li>
            ))}
          </ul>
        ) : (
          <Absent section={report.reproducibility} />
        )}
        <p className="mt-3 text-sm text-muted-foreground">
          The random seed used for this run is not recorded by the platform, so this
          report does not state one.
        </p>
      </section>

      <div className="print:hidden">
        <Link href={`/model/${modelId}`} className="text-sm text-muted-foreground underline">
          Back to model
        </Link>
      </div>
    </div>
  );
}
