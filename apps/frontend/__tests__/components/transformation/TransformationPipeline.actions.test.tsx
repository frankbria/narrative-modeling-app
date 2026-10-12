import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { mockPipelineFetch } from '@/__tests__/utils/pipelineFetch';
import recipeLists from '@/__tests__/fixtures/recipeLists.json';
import TransformationPipeline from '@/components/transformation/TransformationPipeline';

/**
 * What the user sees when they preview or apply (#855). Every action used to fail
 * against the API (422/404) and only log to the console, so the screen showed nothing.
 */
const fetchMock = () => global.fetch as jest.Mock;

/** Route the action calls; everything else gets the pipeline's mount-time stubs. */
function respond(path: string, body: unknown) {
  const mountTime = fetchMock().getMockImplementation()!;
  fetchMock().mockImplementation(async (url: string, init?: RequestInit) =>
    String(url).endsWith(path) ? { ok: true, json: async () => body } : mountTime(url, init),
  );
}

async function addSteps(...labels: RegExp[]) {
  const user = userEvent.setup();
  render(<TransformationPipeline datasetId="dataset-1" onComplete={onComplete} />);
  for (const label of labels) await user.click(await screen.findByRole('button', { name: label }));
  return user;
}

const addTrimWhitespace = () => addSteps(/add trim whitespace/i);

const onComplete = jest.fn();

beforeEach(() => {
  mockPipelineFetch();
  onComplete.mockReset();
});

describe('TransformationPipeline actions (#855)', () => {
  it('shows the previewed rows in the After table', async () => {
    respond('/transformations/preview', {
      success: true,
      preview_data: [{ name: 'alice', score: 10 }],
      stats_before: { row_count: 2, column_count: 2 },
      stats_after: { row_count: 2, column_count: 2 },
    });
    const user = await addTrimWhitespace();

    await user.click(screen.getByRole('button', { name: /^preview$/i }));
    await user.click(await screen.findByRole('button', { name: /^after$/i }));

    expect(await screen.findByText('alice')).toBeInTheDocument();
  });

  it('shows a failed apply to the user, naming the step', async () => {
    respond('/transformations/apply', { success: false, error: 'Transformations support CSV and Parquet files' });
    const user = await addTrimWhitespace();

    await user.click(screen.getByRole('button', { name: /apply & continue/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Step 1 (trim_whitespace) failed: Transformations support CSV and Parquet files',
    );
    expect(onComplete).not.toHaveBeenCalled();
  });

  it('confirms a successful apply and hands back the same dataset', async () => {
    respond('/transformations/apply', { success: true });
    const user = await addTrimWhitespace();

    await user.click(screen.getByRole('button', { name: /apply & continue/i }));

    expect(await screen.findByText('Applied 1 transformation')).toBeInTheDocument();
    await waitFor(() => expect(onComplete).toHaveBeenCalledWith('dataset-1'));
  });

  it('drops the steps a failed apply already applied, so a retry sends only the rest', async () => {
    let applies = 0;
    const mountTime = fetchMock().getMockImplementation()!;
    fetchMock().mockImplementation(async (url: string, init?: RequestInit) => {
      if (!String(url).endsWith('/transformations/apply')) return mountTime(url, init);
      applies += 1;
      return { ok: true, json: async () => (applies === 1 ? { success: true } : { success: false, error: 'not numeric' }) };
    });
    const user = await addSteps(/add trim whitespace/i, /add remove duplicates/i);

    await user.click(screen.getByRole('button', { name: /apply & continue/i }));

    expect(await screen.findByTestId('pipeline-error')).toHaveTextContent(
      'Applied 1 of 2 steps. Step 2 (remove_duplicates) failed: not numeric',
    );
    // Each label is in the sidebar once; the chain keeps only the step still to apply.
    expect(screen.getAllByText('Trim Whitespace')).toHaveLength(1);
    expect(screen.getAllByText('Remove Duplicates')).toHaveLength(2);
    expect(onComplete).not.toHaveBeenCalled();
  });

  it('shows a failed code export instead of doing nothing', async () => {
    const mountTime = fetchMock().getMockImplementation()!;
    fetchMock().mockImplementation(async (url: string, init?: RequestInit) =>
      String(url).endsWith('/transformations/export-code')
        ? { ok: false, status: 404, json: async () => ({ detail: 'Not Found' }) }
        : mountTime(url, init),
    );
    const user = await addTrimWhitespace();

    await user.click(screen.getByTitle('Export as Code'));

    expect(await screen.findByTestId('pipeline-error')).toHaveTextContent('Not Found');
  });

  it('says when the transformation list could not be loaded', async () => {
    const mountTime = fetchMock().getMockImplementation()!;
    fetchMock().mockImplementation(async (url: string, init?: RequestInit) =>
      String(url).endsWith('/transformations/available')
        ? { ok: false, status: 500, json: async () => ({ detail: 'Internal server error' }) }
        : mountTime(url, init),
    );
    render(<TransformationPipeline datasetId="dataset-1" />);

    expect(await screen.findByText(/could not load the transformations/i)).toBeInTheDocument();
  });

  it('shows a failed recipe save on the page, not behind the closed manager', async () => {
    const mountTime = fetchMock().getMockImplementation()!;
    fetchMock().mockImplementation(async (url: string, init?: RequestInit) =>
      String(url).endsWith('/transformations/recipes')
        ? { ok: false, status: 422, json: async () => ({ detail: 'A recipe needs at least one step' }) }
        : mountTime(url, init),
    );
    const user = await addTrimWhitespace();

    await user.click(screen.getByTitle('Manage Recipes'));
    await user.click(screen.getAllByRole('button', { name: /save recipe/i })[0]);
    await user.type(screen.getByPlaceholderText('Enter a descriptive name'), 'Tidy');
    await user.type(screen.getByPlaceholderText('Describe what this recipe does...'), 'trims');
    await user.click(screen.getAllByRole('button', { name: /save recipe/i }).at(-1)!);

    expect(await screen.findByTestId('pipeline-error')).toHaveTextContent('A recipe needs at least one step');
    expect(screen.queryByText('Recipe Manager')).not.toBeInTheDocument();
  });
});

/**
 * #859: Browse listed from a route that does not exist, so it was always empty, and a
 * recipe was loaded from a field the API does not send. The lists served here are the
 * API's own responses (recipeLists.json).
 */
describe('TransformationPipeline recipes (#859)', () => {
  const mine = recipeLists['GET /transformations/recipes'].response;
  const popular = {
    ...recipeLists['GET /transformations/recipes/popular'].response,
    recipes: [{ ...recipeLists['GET /transformations/recipes/popular'].response.recipes[0], name: 'Crowd favourite', usage_count: 7 }],
  };

  /** Serve the recipe lists by exact path; record every list request made. */
  function serveRecipes(lists: Record<string, unknown>) {
    const requested: string[] = [];
    const mountTime = fetchMock().getMockImplementation()!;
    fetchMock().mockImplementation(async (url: string, init?: RequestInit) => {
      const path = String(url).split('/api/v1').pop()!;
      if (!path.startsWith('/transformations/recipes') || init?.method === 'POST') return mountTime(url, init);
      requested.push(path);
      return path in lists
        ? { ok: true, json: async () => lists[path] }
        : { ok: false, status: 404, json: async () => ({ detail: 'Not Found' }) };
    });
    return requested;
  }

  async function openRecipes() {
    const user = userEvent.setup();
    render(<TransformationPipeline datasetId="dataset-1" onComplete={onComplete} />);
    await user.click(await screen.findByTitle('Manage Recipes'));
    return user;
  }

  it('lists the recipes the API returns, with their step counts', async () => {
    const requested = serveRecipes({ '/transformations/recipes': mine });

    await openRecipes();

    expect(await screen.findByText('Tidy names')).toBeInTheDocument();
    expect(screen.getByText('2 steps')).toBeInTheDocument();
    expect(requested).toEqual(['/transformations/recipes']);
  });

  it('reads each filter from its own route', async () => {
    const requested = serveRecipes({
      '/transformations/recipes': mine,
      '/transformations/recipes?include_public=false': { ...mine, recipes: [] },
      '/transformations/recipes/popular': popular,
    });
    const user = await openRecipes();
    await screen.findByText('Tidy names');

    await user.click(screen.getByRole('button', { name: /popular/i }));
    expect(await screen.findByText('Crowd favourite')).toBeInTheDocument();
    expect(screen.getByText('7 uses')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /my recipes/i }));
    expect(await screen.findByText('No recipes found')).toBeInTheDocument();
    expect(requested).toEqual([
      '/transformations/recipes',
      '/transformations/recipes/popular',
      '/transformations/recipes?include_public=false',
    ]);
  });

  it('builds the pipeline from the steps of the recipe that is picked', async () => {
    serveRecipes({ '/transformations/recipes': mine });
    const user = await openRecipes();

    await user.click(await screen.findByText('Tidy names'));
    expect(screen.queryByText('Recipe Manager')).not.toBeInTheDocument();
    respond('/transformations/preview', { success: true, preview_data: [], stats_before: {}, stats_after: {} });
    await user.click(screen.getByRole('button', { name: /^preview$/i }));

    await waitFor(() => {
      const preview = fetchMock().mock.calls.find(([url]) => String(url).endsWith('/transformations/preview'));
      expect(JSON.parse(preview![1].body).transformation_steps).toEqual([
        { transformation_type: 'trim_whitespace', parameters: { columns: ['name'] } },
        { transformation_type: 'fill_missing', parameters: { columns: ['score'], method: 'mean' } },
      ]);
    });
  });

  it('says so when the recipes cannot be loaded', async () => {
    serveRecipes({});

    await openRecipes();

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load recipes/i);
    expect(screen.queryByText('No recipes found')).not.toBeInTheDocument();
  });

  it('saves a recipe as public when the box is ticked', async () => {
    serveRecipes({ '/transformations/recipes': mine });
    const user = await addTrimWhitespace();

    await user.click(screen.getByTitle('Manage Recipes'));
    await user.click(screen.getAllByRole('button', { name: /save recipe/i })[0]);
    await user.type(screen.getByPlaceholderText('Enter a descriptive name'), 'Tidy');
    await user.type(screen.getByPlaceholderText('Describe what this recipe does...'), 'trims');
    await user.click(screen.getByLabelText(/make this recipe public/i));
    await user.click(screen.getAllByRole('button', { name: /save recipe/i }).at(-1)!);

    await waitFor(() => {
      const saved = fetchMock().mock.calls.find(([url, init]) => String(url).endsWith('/transformations/recipes') && init?.method === 'POST');
      expect(JSON.parse(saved![1].body)).toMatchObject({ name: 'Tidy', is_public: true });
    });
  });
});

