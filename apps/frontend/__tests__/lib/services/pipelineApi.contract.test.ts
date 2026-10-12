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
  previewRequest,
  recipeListPath,
  recipeRequest,
  recipeSteps,
  type RecipeFilter,
} from '@/lib/services/pipelineApi';

type Schema = {
  type?: string;
  properties?: Record<string, Schema>;
  required?: string[];
  items?: Schema;
  $ref?: string;
  anyOf?: Schema[];
};
type Root = Schema & { $defs?: Record<string, Schema> };

const JSON_TYPES: Record<string, (v: unknown) => boolean> = {
  string: (v) => typeof v === 'string',
  integer: (v) => Number.isInteger(v),
  number: (v) => typeof v === 'number',
  boolean: (v) => typeof v === 'boolean',
  array: Array.isArray,
  object: (v) => typeof v === 'object' && v !== null && !Array.isArray(v),
  null: (v) => v === null,
};

/** Check against a pydantic JSON schema: every required key present, no key the model
 * does not declare, each value of the declared JSON type, recursing into objects,
 * arrays and $refs. */
function violations(value: unknown, schema: Schema, root: Root, path = '$'): string[] {
  if (schema.$ref) return violations(value, root.$defs![schema.$ref.split('/').pop()!], root, path);
  if (schema.anyOf) {
    return schema.anyOf.some((s) => violations(value, s, root, path).length === 0)
      ? []
      : [`${path}: matches no allowed shape`];
  }
  if (schema.type && !JSON_TYPES[schema.type]?.(value)) return [`${path}: not ${schema.type}`];
  if (Array.isArray(value) && schema.items) {
    return value.flatMap((v, i) => violations(v, schema.items!, root, `${path}[${i}]`));
  }
  if (value && typeof value === 'object' && schema.properties) {
    const obj = value as Record<string, unknown>;
    const missing = (schema.required ?? []).filter((k) => !(k in obj)).map((k) => `${path}.${k}: missing`);
    const unknown = Object.keys(obj).filter((k) => !(k in schema.properties!)).map((k) => `${path}.${k}: not in the API's model`);
    const nested = Object.entries(obj)
      .filter(([k]) => k in schema.properties!)
      .flatMap(([k, v]) => violations(v, schema.properties![k], root, `${path}.${k}`));
    return [...missing, ...unknown, ...nested];
  }
  return [];
}

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

