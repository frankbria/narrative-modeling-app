/**
 * What a transformation's parameter schema says about its form: how a field is
 * labelled, which input it gets, and whether a value is acceptable. Validation
 * only checks a value; it never converts one.
 */

export interface ParameterField {
  type?: string;
  title?: string;
  description?: string;
  required?: boolean;
  default?: unknown;
  enum?: unknown[];
  items?: { type?: string };
  minimum?: number;
  maximum?: number;
}

export type ParametersSchema = Record<string, ParameterField>;

export type FieldKind = 'multi' | 'select' | 'number' | 'boolean' | 'text';

/** `fill_value` and `fillValue` both become "Fill Value". */
export function formatFieldName(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .trim()
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/** Select option text: `forward_fill` reads "Forward Fill". */
export function optionLabel(option: string): string {
  return option
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function fieldLabel(key: string, field: ParameterField): string {
  return field.title || formatFieldName(key);
}

/** A field is required unless the schema opts out or supplies a default. */
export function isRequired(field: ParameterField): boolean {
  return field.required !== false && !field.default;
}

function mentionsColumn(text: string | undefined): boolean {
  return Boolean(text?.toLowerCase().includes('column'));
}

// A string field about columns gets the dataset's columns even when the backend
// lists no enum for it.
function isColumnField(key: string, field: ParameterField, columns: string[]): boolean {
  if (field.type !== 'string' || field.enum || columns.length === 0) return false;
  return [key, field.title, field.description].some(mentionsColumn);
}

type KindTest = (key: string, field: ParameterField, columns: string[]) => boolean;

// First match wins; anything unmatched is a text input.
const KIND_RULES: Array<[FieldKind, KindTest]> = [
  ['multi', (_key, field) => field.type === 'array' && field.items?.type === 'string'],
  ['select', (key, field, columns) => Boolean(field.enum) || isColumnField(key, field, columns)],
  ['number', (_key, field) => field.type === 'number' || field.type === 'integer'],
  ['boolean', (_key, field) => field.type === 'boolean'],
];

export function fieldKind(key: string, field: ParameterField, columns: string[]): FieldKind {
  const rule = KIND_RULES.find(([, matches]) => matches(key, field, columns));
  return rule ? rule[0] : 'text';
}

export function selectOptions(field: ParameterField, columns: string[]): string[] {
  return (field.enum || columns) as string[];
}

/** Not filled in at all. */
function isMissing(value: unknown): boolean {
  return value === undefined || value === null || value === '';
}

/** Missing, or an empty list. */
function isEmpty(value: unknown): boolean {
  return isMissing(value) || (Array.isArray(value) && value.length === 0);
}

interface TypeRule {
  accepts(value: unknown): boolean;
  message: string;
}

// A Map, not an object: a schema type of "constructor" must find no rule.
const TYPE_RULES = new Map<unknown, TypeRule>([
  ['array', { accepts: (value) => Array.isArray(value), message: 'must be an array' }],
  [
    'number',
    { accepts: (value) => typeof value === 'number' || !isNaN(Number(value)), message: 'must be a number' },
  ],
  ['string', { accepts: (value) => typeof value === 'string', message: 'must be text' }],
]);

function typeProblem(field: ParameterField, value: unknown): string | undefined {
  const rule = TYPE_RULES.get(field.type);
  return rule && !rule.accepts(value) ? rule.message : undefined;
}

function enumProblem(field: ParameterField, value: unknown): string | undefined {
  return field.enum && !field.enum.includes(value)
    ? `must be one of: ${field.enum.join(', ')}`
    : undefined;
}

function minimumProblem(field: ParameterField, value: number): string | undefined {
  return field.minimum !== undefined && value < field.minimum
    ? `must be at least ${field.minimum}`
    : undefined;
}

function maximumProblem(field: ParameterField, value: number): string | undefined {
  return field.maximum !== undefined && value > field.maximum
    ? `must be no more than ${field.maximum}`
    : undefined;
}

function rangeProblem(field: ParameterField, value: unknown): string | undefined {
  if (field.type !== 'number' || typeof value !== 'number') return undefined;
  return maximumProblem(field, value) || minimumProblem(field, value);
}

// When several checks fail the first of these wins.
function fieldProblem(field: ParameterField, value: unknown): string | undefined {
  if (isRequired(field) && isEmpty(value)) return 'is required';
  if (isMissing(value)) return undefined;
  return [rangeProblem(field, value), enumProblem(field, value), typeProblem(field, value)].find(Boolean);
}

/** One message per failing field, keyed by parameter name. */
export function validateParameters(
  schema: ParametersSchema,
  parameters: Record<string, unknown>
): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const [key, field] of Object.entries(schema)) {
    const problem = fieldProblem(field, parameters[key]);
    if (problem) errors[key] = `${formatFieldName(key)} ${problem}`;
  }
  return errors;
}
