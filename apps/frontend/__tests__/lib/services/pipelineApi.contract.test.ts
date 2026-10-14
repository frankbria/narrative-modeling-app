/**
 * Every payload the Prepare stage posts must match the request model of the route it
 * posts to (#855). The UI sent `{dataset_id, transformations: [...]}` to preview and
 * apply and its recipes to a route that does not exist; nothing tied the two sides
 * together, so preview and apply 422'd and recipe save 404'd while every suite stayed
 * green. `transformationRequestSchemas.json` is the API's own JSON schema for each
 * route, captured and kept current by the backend's
 * `test_transformation_request_schemas_fixture.py`.
 */
import schemas from '@/__tests__/fixtures/transformationRequestSchemas.json';
import available from '@/__tests__/fixtures/availableTransformations.json';
import recipeLists from '@/__tests__/fixtures/recipeLists.json';
import {
  applyRequest,
  exportRequest,
  fetchRecipes,
  fetchRecipePages,
  previewRequest,
  recipeListPath,
  recipeRequest,
  recipeSteps,
  type RecipeFilter,
} from '@/lib/services/pipelineApi';
import { violations, type Root } from '@/__tests__/utils/jsonSchema';

const steps = [
  { type: 'trim_whitespace', parameters: { columns: ['name'] } },
  { type: 'fill_missing', parameters: { columns: ['score'], method: 'mean' } },
];
const routes = schemas as Record<string, Root>;

it('the payloads are built from types the engine executes', () => {
  const executable = new Set(available.map((t) => t.type));
  expect(steps.filter((s) => !executable.has(s.type))).toEqual([]);
});

describe('Prepare-stage payloads match the API request models', () => {
  it('preview', () => {
    const schema = routes['POST /transformations/preview'];
    expect(violations(previewRequest('ds1', steps), schema, schema)).toEqual([]);
  });

  it('apply (one request per pipeline step)', () => {
    const schema = routes['POST /transformations/apply'];
    for (const step of steps) {
      expect(violations(applyRequest('ds1', step), schema, schema)).toEqual([]);
    }
  });

  it('recipe save', () => {
    const schema = routes['POST /transformations/recipes'];
    const body = recipeRequest({ name: 'Clean', description: 'tidy', datasetId: 'ds1', steps });
    expect(violations(body, schema, schema)).toEqual([]);
  });

  it('export as code', () => {
    const schema = routes['POST /transformations/export-code'];
    expect(violations(exportRequest(steps), schema, schema)).toEqual([]);
  });

  it('export as code: the body the button used to send is not the model', () => {
    const schema = routes['POST /transformations/export-code'];
    expect(violations({ transformations: steps }, schema, schema)).toEqual([
      '$.steps: missing',
      "$.transformations: not in the API's model",
    ]);
  });

  it('the checker itself rejects the payload shape that used to ship', () => {
    const schema = routes['POST /transformations/preview'];
    const old = { dataset_id: 'ds1', transformations: steps };
    expect(violations(old, schema, schema)).toEqual([
      '$.transformation_steps: missing',
      "$.transformations: not in the API's model",
    ]);
  });

  it('the checker itself rejects a value of the wrong type', () => {
    const schema = routes['POST /transformations/apply'];
    const wrong = { dataset_id: 42, transformation_type: 'trim_whitespace', parameters: [] };
    expect(violations(wrong, schema, schema)).toEqual(['$.dataset_id: not string', '$.parameters: matches no allowed shape']);
  });
});

/**
 * #859: the recipe browser listed from `GET /recipes?filter=…&dataset_id=…`, which is no
 * route, and loading a recipe read `recipe.transformations` where the API sends `steps`.
 * `recipeLists.json` holds each list route's query parameters and a real response,
 * captured by the backend's `test_recipe_list_response_fixture.py`.
 */
describe('Recipe browsing reads the routes the API has (#859)', () => {
  const lists = recipeLists as unknown as Record<string, { query: string[]; response: unknown }>;

  it.each<RecipeFilter>(['all', 'mine', 'popular'])('%s: a route that exists, with query parameters it declares', (filter) => {
    const [path, query = ''] = recipeListPath(filter).split('?');
    const route = lists[`GET ${path}`];

    expect(route).toBeDefined();
    expect([...new URLSearchParams(query).keys()].filter((name) => !route.query.includes(name))).toEqual([]);
  });

  it('a later page names itself after any query already there (#929)', () => {
    expect(recipeListPath('all', 2)).toBe('/transformations/recipes?page=2');
    expect(recipeListPath('mine', 3)).toBe('/transformations/recipes?include_public=false&page=3');
    expect(recipeListPath('mine', 1)).toBe('/transformations/recipes?include_public=false');
  });

  it('popular is one request however many pages are asked for (#929)', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => lists['GET /transformations/recipes/popular'].response,
    });

    const shown = await fetchRecipePages('popular', 3);

    expect((global.fetch as jest.Mock).mock.calls).toHaveLength(1);
    expect(shown.recipes.length).toBe(shown.total);
  });

  it('"mine" leaves other accounts\' public recipes out, and "all" does not', () => {
    expect(recipeListPath('mine')).toBe('/transformations/recipes?include_public=false');
    expect(recipeListPath('all')).toBe('/transformations/recipes');
  });

  it.each<RecipeFilter>(['all', 'popular'])('%s: a recipe from a real response gives the pipeline its steps', async (filter) => {
    const response = lists[`GET ${recipeListPath(filter)}`].response;
    (global.fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => response });

    const [recipe] = await fetchRecipes(filter);

    expect(recipe.name).toBe('Tidy names');
    expect(recipeSteps(recipe)).toEqual(steps);
    expect(String((global.fetch as jest.Mock).mock.calls[0][0])).toMatch(new RegExp(`${recipeListPath(filter).replace('?', '\\?')}$`));
  });

  it('a recipe can be saved as public, in the field the API reads', () => {
    const schema = routes['POST /transformations/recipes'];
    const body = recipeRequest({ name: 'Clean', description: 'tidy', datasetId: 'ds1', steps, isPublic: true });

    expect(violations(body, schema, schema)).toEqual([]);
    expect(body.is_public).toBe(true);
  });
});

