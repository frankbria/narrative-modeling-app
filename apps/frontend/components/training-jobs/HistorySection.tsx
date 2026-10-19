import type { ChangeEvent } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { TrainingJobSummary } from '@/lib/services/model';
import {
  algorithmText,
  durationText,
  scoreText,
  statusBadgeVariant,
  type HistoryFilter,
} from './trainingJobs';

interface HistoryRowProps {
  job: TrainingJobSummary;
}

function HistoryRow(props: HistoryRowProps) {
  const { job } = props;
  return (
    <TableRow>
      <TableCell>
        <Badge variant={statusBadgeVariant(job.status)}>{job.status}</Badge>
      </TableCell>
      <TableCell>
        <span className="font-medium">{job.target_column}</span>
        <span className="block text-xs text-muted-foreground">Dataset {job.dataset_id}</span>
      </TableCell>
      <TableCell>{durationText(job)}</TableCell>
      <TableCell>{algorithmText(job)}</TableCell>
      <TableCell>{scoreText(job)}</TableCell>
      <TableCell>{new Date(job.created_at).toLocaleString()}</TableCell>
    </TableRow>
  );
}

interface HistoryTableProps {
  jobs: TrainingJobSummary[];
}

function HistoryTable(props: HistoryTableProps) {
  const { jobs } = props;
  const renderRow = (job: TrainingJobSummary) => <HistoryRow key={job.model_id} job={job} />;
  if (jobs.length === 0) {
    return <p className="text-sm text-muted-foreground">No finished training jobs yet.</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Status</TableHead>
          <TableHead>Target</TableHead>
          <TableHead>Duration</TableHead>
          <TableHead>Best Algorithm</TableHead>
          <TableHead>Score</TableHead>
          <TableHead>Created</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>{jobs.map(renderRow)}</TableBody>
    </Table>
  );
}

interface FilterSelectProps {
  value: HistoryFilter;
  onChange(filter: HistoryFilter): void;
}

function FilterSelect(props: FilterSelectProps) {
  const { value, onChange } = props;
  const handleChange = (e: ChangeEvent<HTMLSelectElement>) => onChange(e.target.value as HistoryFilter);
  return (
    <select
      aria-label="Filter by status"
      value={value}
      onChange={handleChange}
      className="p-2 text-sm border border-border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
    >
      <option value="all">All</option>
      <option value="completed">Completed</option>
      <option value="failed">Failed</option>
      <option value="cancelled">Cancelled</option>
    </select>
  );
}

interface LoadMoreProps {
  hasMore: boolean;
  isLoadingMore: boolean;
  onLoadMore: VoidFunction;
}

function LoadMore(props: LoadMoreProps) {
  const { hasMore, isLoadingMore, onLoadMore } = props;
  if (!hasMore) return null;
  return (
    <div className="flex justify-center">
      <Button variant="outline" disabled={isLoadingMore} onClick={onLoadMore}>
        {isLoadingMore ? 'Loading…' : 'Load more'}
      </Button>
    </div>
  );
}

interface HistorySectionProps {
  jobs: TrainingJobSummary[];
  statusFilter: HistoryFilter;
  hasMore: boolean;
  isLoadingMore: boolean;
  onFilterChange(filter: HistoryFilter): void;
  onLoadMore: VoidFunction;
}

/** A filterable, paginated table of completed/failed/cancelled jobs. */
export function HistorySection(props: HistorySectionProps) {
  const { jobs, statusFilter, hasMore, isLoadingMore, onFilterChange, onLoadMore } = props;
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Training History</h2>
        <FilterSelect value={statusFilter} onChange={onFilterChange} />
      </div>
      <HistoryTable jobs={jobs} />
      <LoadMore hasMore={hasMore} isLoadingMore={isLoadingMore} onLoadMore={onLoadMore} />
    </section>
  );
}
