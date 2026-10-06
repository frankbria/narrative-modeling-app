/**
 * The Prepare stage's API calls (#855): which routes, in what order, and what the UI
 * gets back. The payload shapes themselves are pinned by pipelineApi.contract.test.ts.
 */
import { API_URL } from '@/lib/constants';
import {
  applyPipeline,
  fetchDatasetRows,
  fetchTransformationTypes,
  previewPipeline,
  saveRecipe,
} from '@/lib/services/pipelineApi';

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body });
const fetchMock = () => global.fetch as jest.Mock;
const steps = [
  { type: 'trim_whitespace', parameters: {} },
  { type: 'fill_missing', parameters: { method: 'mean' } },
];

beforeEach(() => fetchMock().mockReset());

describe('previewPipeline', () => {
  it('posts every step at once and adapts the response for the preview panel', async () => {
    fetchMock().mockResolvedValueOnce(ok({
      success: true,
      preview_data: [{ name: 'alice', score: 10 }, { name: 'bob', score: 20 }],
      stats_before: { row_count: 2, column_count: 2 },
      stats_after: { row_count: 2, column_count: 2 },
    }));
    const before = { columns: ['name', 'score'], data: [[' alice ', 10]] };

    const preview = await previewPipeline('ds1', steps, before);

    const [url, init] = fetchMock().mock.calls[0];
    expect(url).toBe(`${API_URL}/transformations/preview`);
    expect(JSON.parse(init.body).transformation_steps).toHaveLength(2);
    expect(preview.before).toBe(before);
    // Records from the API become rows of cells, in column order, for PreviewPanel.
    expect(preview.after).toEqual({ columns: ['name', 'score'], data: [['alice', 10], ['bob', 20]] });
    expect(preview.summary).toEqual({ rows_before: 2, rows_after: 2, cols_before: 2, cols_after: 2 });
  });

  it('throws the API error a failed preview reports', async () => {
    fetchMock().mockResolvedValueOnce(ok({ success: false, error: 'Column score is not numeric' }));
    await expect(previewPipeline('ds1', steps, null)).rejects.toThrow('Column score is not numeric');
  });

  it('throws on an HTTP failure', async () => {
    fetchMock().mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({ detail: 'Dataset not found' }) });
    await expect(previewPipeline('ds1', steps, null)).rejects.toThrow('Dataset not found');
  });
});

describe('applyPipeline', () => {
  it('applies each step as its own request, in order, so each is a history step', async () => {
    fetchMock().mockResolvedValue(ok({ success: true }));

    await applyPipeline('ds1', steps);

    const bodies = fetchMock().mock.calls.map(([url, init]) => [url, JSON.parse(init.body).transformation_type]);
    expect(bodies).toEqual([
      [`${API_URL}/transformations/apply`, 'trim_whitespace'],
      [`${API_URL}/transformations/apply`, 'fill_missing'],
    ]);
  });

  it('stops at the first failed step and names it', async () => {
    fetchMock()
      .mockResolvedValueOnce(ok({ success: false, error: 'Transformations support CSV and Parquet files' }))
      .mockResolvedValue(ok({ success: true }));

    await expect(applyPipeline('ds1', steps)).rejects.toThrow(
      'Step 1 (trim_whitespace) failed: Transformations support CSV and Parquet files',
    );
    expect(fetchMock()).toHaveBeenCalledTimes(1);
  });
});

describe('saveRecipe', () => {
  it('posts to the recipes route', async () => {
    fetchMock().mockResolvedValueOnce(ok({ recipe_id: 'r1' }));
    await saveRecipe({ name: 'Clean', description: '', datasetId: 'ds1', steps });
    expect(fetchMock().mock.calls[0][0]).toBe(`${API_URL}/transformations/recipes`);
  });

  it('throws when the save fails', async () => {
    fetchMock().mockResolvedValueOnce({ ok: false, status: 422, json: async () => ({ detail: 'name required' }) });
    await expect(saveRecipe({ name: '', description: '', datasetId: 'ds1', steps })).rejects.toThrow('name required');
  });
});

describe('reference data', () => {
  it('reads /transformations/available as the list it is', async () => {
    fetchMock().mockResolvedValueOnce(ok([{ type: 'trim_whitespace', category: 'Data Cleaning', label: 'Trim Whitespace' }]));
    expect((await fetchTransformationTypes()).map((t) => t.type)).toEqual(['trim_whitespace']);
  });

  it('reads the dataset preview rows with plain column names', async () => {
    fetchMock().mockResolvedValueOnce(ok({ columns: ['score', 'name'], data: [{ name: 'a', score: 1 }] }));
    expect(await fetchDatasetRows('ds1')).toEqual({ columns: ['score', 'name'], data: [[1, 'a']] });
    expect(fetchMock().mock.calls[0][0]).toBe(`${API_URL}/data/ds1/preview`);
  });
});
