/** A checker for the pydantic JSON schemas the backend captures into `__tests__/fixtures`. */

export type Schema = {
  type?: string;
  properties?: Record<string, Schema>;
  required?: string[];
  items?: Schema;
  $ref?: string;
  anyOf?: Schema[];
};
export type Root = Schema & { $defs?: Record<string, Schema> };

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
export function violations(value: unknown, schema: Schema, root: Root, path = '$'): string[] {
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
