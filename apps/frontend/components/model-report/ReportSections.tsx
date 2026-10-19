/**
 * The sections of the model report page (#795), one component each.
 *
 * Their shared job is to preserve provenance: a section the platform never recorded
 * renders as an explicit "Not recorded" with its reason, never as an empty table,
 * which would read as "nothing else was tried" (#536).
 */
import type { ModelReport, ReportSection } from '@/lib/types/modelReport';

type Report = { report: ModelReport };

const HEADING = 'mb-3 text-lg font-semibold text-foreground';
const ROW = 'flex justify-between border-b border-border py-1';

export function num(value: number | null | undefined, digits = 4): string {
  return value === null || value === undefined ? '—' : value.toFixed(digits);
}

function orDash(value: number | null | undefined): number | string {
  return value ?? '—';
}

export function Absent(props: { section: ReportSection }) {
  const { section } = props;
  return (
    <div className="rounded-md border border-border bg-muted p-4">
      <p className="text-sm font-medium text-foreground">Not recorded</p>
      {section.note && <p className="mt-1 text-sm text-muted-foreground">{section.note}</p>}
    </div>
  );
}

function ExcludedColumns(props: { label: string; columns: string[] | undefined }) {
  const columns = props.columns ?? [];
  if (columns.length === 0) return null;
  return (
    <div className="col-span-3">
      <dt className="text-muted-foreground">{props.label}</dt>
      <dd className="text-foreground">{columns.join(', ')}</dd>
    </div>
  );
}

export function DataSection(props: Report) {
  const { dataset } = props.report;
  return (
    <section className="mb-8">
      <h2 className={HEADING}>The data</h2>
      <dl className="grid grid-cols-3 gap-4 text-sm">
        <div>
          <dt className="text-muted-foreground">Target</dt>
          <dd className="text-foreground">{dataset.target_column}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Training rows</dt>
          <dd className="text-foreground">{orDash(dataset.n_samples_train)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Features</dt>
          <dd className="text-foreground">{orDash(dataset.n_features)}</dd>
        </div>
        <ExcludedColumns label="Excluded as identifiers" columns={dataset.excluded_columns} />
        <ExcludedColumns label="Excluded as dates" columns={dataset.excluded_date_columns} />
        <ExcludedColumns label="Excluded as empty" columns={dataset.excluded_empty_columns} />
        <ExcludedColumns label="Left out by you" columns={dataset.excluded_user_columns} />
        <ExcludedColumns label="Interaction features" columns={dataset.interaction_features} />
      </dl>
    </section>
  );
}

function LeaderboardTable(props: { rows: ModelReport['leaderboard']['rows'] }) {
  const { rows } = props;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-border text-left text-muted-foreground">
          <th className="py-2">Algorithm</th>
          <th className="py-2">CV score</th>
          <th className="py-2">Test score</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.algorithm} className="border-b border-border">
            <td className="py-2 text-foreground">
              {row.algorithm}
              {row.is_winner && (
                <span className="ml-2 text-xs font-medium text-muted-foreground">winner</span>
              )}
            </td>
            <td className="py-2 text-foreground">{num(row.cv_score)}</td>
            <td className="py-2 text-foreground">{num(row.test_score)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function LeaderboardSection(props: Report) {
  const { leaderboard } = props.report;
  const recorded = leaderboard.rows.length > 0;
  return (
    <section className="mb-8">
      <h2 className={HEADING}>Algorithms tried</h2>
      {recorded && <LeaderboardTable rows={leaderboard.rows} />}
      {!recorded && <Absent section={leaderboard} />}
    </section>
  );
}

export function BaselineSection(props: Report) {
  const { baseline } = props.report;
  const computed = baseline.score !== null;
  return (
    <section className="mb-8">
      <h2 className={HEADING}>Baseline</h2>
      {computed && (
        <p className="text-sm text-foreground">
          A no-skill <strong>{baseline.strategy}</strong> predictor scores{' '}
          <strong>{num(baseline.score)}</strong> ({baseline.metric}) on the same held-out rows.
          <span className="mt-1 block text-muted-foreground">{baseline.note}</span>
        </p>
      )}
      {!computed && <Absent section={baseline} />}
    </section>
  );
}

/**
 * The winner's settings (#801). `null` means this model did not record them; an
 * empty object is a recorded fact: the algorithm ran on its library defaults.
 */
function Hyperparameters(props: { values: Record<string, unknown> | null | undefined }) {
  const { values } = props;
  if (values === null || values === undefined) {
    return (
      <p className="mt-2 text-sm italic text-muted-foreground">
        The winning algorithm&apos;s hyperparameters were not recorded for this model.
      </p>
    );
  }
  const entries = Object.entries(values).sort(([a], [b]) => a.localeCompare(b));
  if (entries.length === 0) {
    return (
      <p className="mt-2 text-sm text-muted-foreground">
        The winning algorithm ran on its library defaults: no hyperparameters were set.
      </p>
    );
  }
  return (
    <ul className="mt-3 space-y-1 text-sm" aria-label="Hyperparameters">
      {entries.map(([name, value]) => (
        <li key={name} className={ROW}>
          <span className="text-foreground">{name}</span>
          <span className="text-muted-foreground">{String(value)}</span>
        </li>
      ))}
    </ul>
  );
}

export function WinnerSection(props: Report) {
  const { winner } = props.report;
  return (
    <section className="mb-8">
      <h2 className={HEADING}>Why this model</h2>
      <p className="text-sm text-foreground">
        <strong>{winner.algorithm}</strong> — CV {num(winner.cv_score)}, test{' '}
        {num(winner.test_score)}.
      </p>
      {winner.explanation && (
        <p className="mt-2 text-sm text-muted-foreground">{winner.explanation}</p>
      )}
      {/* The winner's numbers ARE stored; only the narrative is missing. The Absent
          block here would print the "Not recorded" used for genuinely absent
          sections, which is the mislabelling this design exists to prevent. */}
      {!winner.explanation && (
        <p className="mt-2 text-sm italic text-muted-foreground">
          {winner.note ?? 'No stored explanation of why this algorithm won.'}
        </p>
      )}
      <Hyperparameters values={winner.hyperparameters} />
    </section>
  );
}

function DriverList(props: { drivers: ModelReport['drivers'] }) {
  const { drivers } = props;
  return (
    <>
      {/* The truncation note must appear here too: "Print / Save as PDF" IS this
          page, so without it the PDF shows 20 rows implying "here are the drivers". */}
      {drivers.note && <p className="mb-2 text-sm text-muted-foreground">{drivers.note}</p>}
      <ul className="space-y-1 text-sm">
        {drivers.features.map(([name, value]) => (
          <li key={name} className={ROW}>
            <span className="text-foreground">{name}</span>
            <span className="text-muted-foreground">{num(value)}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

export function DriversSection(props: Report) {
  const { drivers } = props.report;
  const recorded = drivers.features.length > 0;
  return (
    <section className="mb-8">
      <h2 className={HEADING}>What drives it</h2>
      {recorded && <DriverList drivers={drivers} />}
      {!recorded && <Absent section={drivers} />}
    </section>
  );
}

export function CaveatsSection(props: Report) {
  const { caveats } = props.report;
  if (caveats.length === 0) return null;
  return (
    <section className="mb-8">
      <h2 className={HEADING}>Caveats</h2>
      <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
        {caveats.map((caveat) => (
          <li key={caveat}>{caveat}</li>
        ))}
      </ul>
    </section>
  );
}

/** The seed training used (#801), or a plain statement that this model has none. */
function SeedLine(props: { seed: number | null | undefined }) {
  const { seed } = props;
  if (typeof seed !== 'number') {
    return (
      <p>
        The random seed used for this run is not recorded for this model, so this report
        does not state one.
      </p>
    );
  }
  return (
    <p>
      Random seed: <strong className="text-foreground">{seed}</strong>
    </p>
  );
}

/** The dataset version trained on (#801). A model without one says so under Caveats. */
function VersionLine(props: { version: string | null | undefined }) {
  const { version } = props;
  if (!version) return null;
  return (
    <p>
      Dataset version: <code className="text-foreground">{version}</code>
    </p>
  );
}

export function ReproducibilitySection(props: Report) {
  const { reproducibility } = props.report;
  const versions = Object.entries(reproducibility.environment);
  return (
    <section className="mb-8">
      <h2 className={HEADING}>Reproducibility</h2>
      {versions.length > 0 && (
        <ul className="space-y-1 text-sm">
          {versions.map(([k, v]) => (
            <li key={k} className={ROW}>
              <span className="text-foreground">{k}</span>
              <span className="text-muted-foreground">{v}</span>
            </li>
          ))}
        </ul>
      )}
      {versions.length === 0 && <Absent section={reproducibility} />}
      <div className="mt-3 space-y-1 text-sm text-muted-foreground">
        <SeedLine seed={reproducibility.seed} />
        <VersionLine version={reproducibility.dataset_version_id} />
      </div>
    </section>
  );
}
