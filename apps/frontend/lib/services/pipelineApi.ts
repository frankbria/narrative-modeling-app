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

/** A recipe to save: the pipeline's steps under a name, optionally shared with other accounts. */
export interface NewRecipe {
  name: string;
  description: string;
  datasetId: string;
  steps: PipelineStep[];
  isPublic?: boolean;
}

export function recipeRequest(recipe: NewRecipe) {
  return {
    name: recipe.name,
    description: recipe.description,
    dataset_id: recipe.datasetId,
    is_public: recipe.isPublic === true,
    steps: recipe.steps.map((s) => ({ type: s.type, parameters: s.parameters })),
  };
}

/** Which recipes the browser lists: the caller's and every public one, the caller's
 * only, or the most used public ones. */
export type RecipeFilter = 'all' | 'mine' | 'popular';

/** A saved recipe as the recipe list routes return it: the fields the browser reads. */
export interface SavedRecipe {
  id: string;
  name: string;
  description: string | null;
  steps: { type: string; parameters: Record<string, unknown> }[];
  created_at: string;
  is_public: boolean;
  usage_count: number;
}

const RECIPE_LISTS: Record<RecipeFilter, string> = {
  all: '/transformations/recipes',
  mine: '/transformations/recipes?include_public=false',
  popular: '/transformations/recipes/popular',
};

/** The route a filter reads. The browser used to ask `GET /recipes?filter=…`, which is
 * no route, so it was always empty (#859); recipeLists.json pins these to the API. */
export function recipeListPath(filter: RecipeFilter): string {
  return RECIPE_LISTS[filter];
}

export async function fetchRecipes(filter: RecipeFilter): Promise<SavedRecipe[]> {
  const body = await get<{ recipes: SavedRecipe[] }>(recipeListPath(filter), 'the request failed');
  return body.recipes;
}

/** The pipeline a saved recipe describes. The API sends `steps`, each with a `type`. */
export function recipeSteps(recipe: SavedRecipe): PipelineStep[] {
  return recipe.steps.map((s) => ({ type: s.type, parameters: s.parameters }));
}

/** The API returns records; the panel draws arrays in column order. */
function table(rows: Record<string, unknown>[], columns: string[] = Object.keys(rows[0] ?? {})): PreviewTable {
  return { columns, data: rows.map((row) => columns.map((c) => row[c])) };
}

const count = (value: number | undefined) => value ?? 0;

function summary(before: Stats | undefined, after: Stats | undefined): PipelinePreview['summary'] {
  if (!before || !after) return null;
  return {
    rows_before: count(before.row_count),
    rows_after: count(after.row_count),
    cols_before: count(before.column_count),
    cols_after: count(after.column_count),
  };
}

function adaptPreview(result: Record<string, unknown>, before: PreviewTable | null): PipelinePreview {
  const rows = (result.preview_data as Record<string, unknown>[] | null) ?? [];
  return {
    before,
    // No rows left: no record to read the columns from, so keep the dataset's.
    after: table(rows, rows.length ? undefined : before?.columns),
    summary: summary(result.stats_before as Stats | undefined, result.stats_after as Stats | undefined),
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
  return adaptPreview(result, before);
}

/** A pipeline apply that stopped part-way. `applied` steps are already in the dataset's
 * history, so the caller must not send them again. */
export class PipelineApplyError extends Error {
  constructor(
    readonly applied: number,
    total: number,
    step: PipelineStep,
    reason: string,
  ) {
    const done = applied > 0 ? `Applied ${applied} of ${total} steps. ` : '';
    super(`${done}Step ${applied + 1} (${step.type}) failed: ${reason}`);
    this.name = 'PipelineApplyError';
  }
}

async function applyStep(datasetId: string, step: PipelineStep): Promise<void> {
  const result = await post('/transformations/apply', applyRequest(datasetId, step), 'Apply failed');
  if (result.success === false) throw new Error(String(result.error ?? 'unknown error'));
}

/** Apply each step as its own request, in order, so each becomes a history step that
 * undo can reach (#800). Stops at the first failure, naming the step and how many
 * steps before it are already applied. */
export async function applyPipeline(datasetId: string, steps: PipelineStep[]): Promise<void> {
  for (const [index, step] of steps.entries()) {
    try {
      await applyStep(datasetId, step);
    } catch (e) {
      throw new PipelineApplyError(index, steps.length, step, (e as Error).message);
    }
  }
}

export async function saveRecipe(recipe: NewRecipe): Promise<void> {
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

export function exportRequest(steps: PipelineStep[]) {
  return { steps: steps.map((s) => ({ type: s.type, parameters: s.parameters })) };
}

function download(filename: string, text: string): void {
  const url = window.URL.createObjectURL(new Blob([text], { type: 'text/x-python' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
}

/** Download the pipeline as a Python script. A failure throws, so the page shows it
 * instead of the button silently doing nothing. The button used to post to this path
 * before any route served it (#860). */
export async function exportPipelineCode(steps: PipelineStep[]): Promise<void> {
  const script = await post('/transformations/export-code', exportRequest(steps), 'Exporting the pipeline as code failed');
  download(String(script.filename), String(script.code));
}
