/**
 * The Prepare stage's calls to the transformation API (#855).
 *
 * The pipeline component used to build these inline, and none matched a route: preview
 * and apply posted `{dataset_id, transformations: [...]}` (422), recipe save went to a
 * route that does not exist (404), `/transformations/available` was read as an object
 * when it is a list, and the dataset's columns as objects when they are names. Every
 * payload here is pinned to the API's request models by pipelineApi.contract.test.ts.
 */
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { apiError } from '@/lib/services/apiError';

/** One node of the pipeline: a registry transformation type and its parameters. */
export interface PipelineStep {
  type: string;
  parameters: Record<string, unknown>;
}

/** A transformation type as GET /transformations/available returns it. */
export interface TransformationTypeMeta {
  type: string;
  category: string;
  label: string;
  description?: string;
  parameters_schema?: Record<string, unknown>;
  requires_columns?: boolean;
}

/** What PreviewPanel draws: a header row and the cells of each row, in column order. */
export interface PreviewTable {
  columns: string[];
  data: unknown[][];
}

/** What PreviewPanel renders. */
export interface PipelinePreview {
  before: PreviewTable | null;
  after: PreviewTable | null;
  summary: { rows_before: number; rows_after: number; cols_before: number; cols_after: number } | null;
}

interface Stats {
  row_count?: number;
  column_count?: number;
}

async function headers(): Promise<Record<string, string>> {
  const token = await getAuthToken();
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };
}

async function post(path: string, body: unknown, fallback: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: await headers(),
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await apiError(response, fallback);
  return response.json();
}

async function get<T>(path: string, fallback: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { headers: await headers() });
  if (!response.ok) throw await apiError(response, fallback);
  return response.json();
}

export function previewRequest(datasetId: string, steps: PipelineStep[]) {
  return {
    dataset_id: datasetId,
    transformation_steps: steps.map((s) => ({ transformation_type: s.type, parameters: s.parameters })),
  };
}

export function applyRequest(datasetId: string, step: PipelineStep) {
  return { dataset_id: datasetId, transformation_type: step.type, parameters: step.parameters };
}

export function recipeRequest(recipe: { name: string; description: string; datasetId: string; steps: PipelineStep[] }) {
  return {
    name: recipe.name,
    description: recipe.description,
    dataset_id: recipe.datasetId,
    steps: recipe.steps.map((s) => ({ type: s.type, parameters: s.parameters })),
  };
}

/** The API returns records; the panel draws arrays in column order. */
function table(rows: Record<string, unknown>[], columns: string[] = Object.keys(rows[0] ?? {})): PreviewTable {
  return { columns, data: rows.map((row) => columns.map((c) => row[c])) };
}

function summary(before: Stats | undefined, after: Stats | undefined): PipelinePreview['summary'] {
  if (!before || !after) return null;
  return {
    rows_before: before.row_count ?? 0,
    rows_after: after.row_count ?? 0,
    cols_before: before.column_count ?? 0,
    cols_after: after.column_count ?? 0,
  };
}

/** Preview the whole pipeline on the dataset; `before` is the untransformed rows. */
export async function previewPipeline(
  datasetId: string,
  steps: PipelineStep[],
  before: PreviewTable | null,
): Promise<PipelinePreview> {
  const result = await post('/transformations/preview', previewRequest(datasetId, steps), 'Preview failed');
  if (result.success === false) throw new Error(String(result.error ?? 'Preview failed'));
  return {
    before,
    after: table((result.preview_data as Record<string, unknown>[] | null) ?? []),
    summary: summary(result.stats_before as Stats | undefined, result.stats_after as Stats | undefined),
  };
}

/** Apply each step as its own request, in order, so each becomes a history step that
 * undo can reach (#800). Stops at the first failure and names the step. */
export async function applyPipeline(datasetId: string, steps: PipelineStep[]): Promise<void> {
  for (const [index, step] of steps.entries()) {
    const result = await post('/transformations/apply', applyRequest(datasetId, step), `Step ${index + 1} failed`);
    if (result.success === false) {
      throw new Error(`Step ${index + 1} (${step.type}) failed: ${String(result.error ?? 'unknown error')}`);
    }
  }
}

export async function saveRecipe(recipe: {
  name: string;
  description: string;
  datasetId: string;
  steps: PipelineStep[];
}): Promise<void> {
  await post('/transformations/recipes', recipeRequest(recipe), 'Saving the recipe failed');
}

export async function fetchTransformationTypes(): Promise<TransformationTypeMeta[]> {
  return get<TransformationTypeMeta[]>('/transformations/available', 'Could not load transformations');
}

/** The dataset's first rows, as the "before" table and the column list. */
export async function fetchDatasetRows(datasetId: string): Promise<PreviewTable> {
  const body = await get<{ columns: string[]; data: Record<string, unknown>[] }>(
    `/data/${datasetId}/preview`,
    'Could not load the dataset preview',
  );
  return table(body.data, body.columns);
}
