import { TrainingProgress } from '@/components/training/TrainingProgress';
import { CancelTrainingButton } from '@/components/training/CancelTrainingButton';
import { Badge } from '@/components/ui/badge';
import type { TrainingJobSummary } from '@/lib/services/model';

interface InFlightCardProps {
  job: TrainingJobSummary;
  onSettled: VoidFunction;
  onCancelled: VoidFunction;
}

function InFlightCard(props: InFlightCardProps) {
  const { job, onSettled, onCancelled } = props;
  return (
    <div className="border border-border rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium truncate">{job.target_column}</p>
          <p className="text-xs text-muted-foreground truncate">Dataset {job.dataset_id}</p>
        </div>
        <Badge variant="outline">{job.status}</Badge>
      </div>
      <TrainingProgress
        modelId={job.model_id}
        compact
        onComplete={onSettled}
        onError={onSettled}
        onCancelled={onSettled}
      />
      <CancelTrainingButton modelId={job.model_id} onCancelled={onCancelled} className="w-full" />
    </div>
  );
}

interface InFlightSectionProps {
  jobs: TrainingJobSummary[];
  isLoading: boolean;
  /** A card's job finished (completed/failed/cancelled). */
  onSettled: VoidFunction;
  /** The user cancelled a job. */
  onCancelled: VoidFunction;
}

function InFlightBody(props: InFlightSectionProps) {
  const { jobs, isLoading, onSettled, onCancelled } = props;
  const renderCard = (job: TrainingJobSummary) => (
    <InFlightCard key={job.model_id} job={job} onSettled={onSettled} onCancelled={onCancelled} />
  );
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading training jobs…</p>;
  }
  if (jobs.length === 0) {
    return <p className="text-sm text-muted-foreground">No training jobs are currently running.</p>;
  }
  return <div className="grid gap-4 md:grid-cols-2">{jobs.map(renderCard)}</div>;
}

/** Pending and running jobs as compact live-progress cards, each with a cancel button. */
export function InFlightSection(props: InFlightSectionProps) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">In-Flight Training</h2>
      <InFlightBody {...props} />
    </section>
  );
}
