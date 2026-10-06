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
import { applyRequest, previewRequest, recipeRequest } from '@/lib/services/pipelineApi';

type Schema = {
  properties?: Record<string, Schema>;
  required?: string[];
  items?: Schema;
  $ref?: string;
  anyOf?: Schema[];
};
type Root = Schema & { $defs?: Record<string, Schema> };

/** Field-name check against a pydantic JSON schema: every required key present, no
 * key the model does not declare, recursing into objects, arrays and $refs. */
function violations(value: unknown, schema: Schema, root: Root, path = '$'): string[] {
  if (schema.$ref) return violations(value, root.$defs![schema.$ref.split('/').pop()!], root, path);
  if (schema.anyOf) {
    return schema.anyOf.some((s) => violations(value, s, root, path).length === 0)
      ? []
      : [`${path}: matches no allowed shape`];
  }
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

  it('the checker itself rejects the payload shape that used to ship', () => {
    const schema = routes['POST /transformations/preview'];
    const old = { dataset_id: 'ds1', transformations: steps };
    expect(violations(old, schema, schema)).toEqual([
      '$.transformation_steps: missing',
      "$.transformations: not in the API's model",
    ]);
  });
});
