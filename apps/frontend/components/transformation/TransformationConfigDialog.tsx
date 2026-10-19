'use client';

import type { ComponentType, MutableRefObject, RefObject } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Eye, Plus, Trash2, AlertCircle } from 'lucide-react';
import {
  fieldKind,
  fieldLabel,
  isRequired,
  optionLabel,
  selectOptions,
  type FieldKind,
  type ParameterField as ParameterSchemaField,
  type ParametersSchema,
} from './parameterSchema';
import { useTransformationForm, type TransformationConfig } from './useTransformationForm';
import { MultiSelect } from './MultiSelect';

export type { TransformationConfig };

export interface TransformationConfigDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  transformationType: string | null;
  transformationLabel: string;
  transformationDescription: string;
  parametersSchema: Record<string, any>;
  availableColumns: string[];
  datasetId: string;
  onAdd: (config: TransformationConfig) => void;
  onPreview?: (config: TransformationConfig) => Promise<void>;
  existingConfig?: TransformationConfig | null;
  onDelete?: () => void;
}

interface FieldProps {
  name: string;
  field: ParameterSchemaField;
  value: any;
  error: string | undefined;
  availableColumns: string[];
  inputRef(el: HTMLInputElement | null): void;
  onChange(key: string, value: unknown): void;
}

interface FieldErrorProps {
  name: string;
  error: string | undefined;
}

interface FieldLabelProps {
  name: string;
  label: string;
  required: boolean;
}

function errorAria(name: string, error: string | undefined) {
  return {
    'aria-invalid': !!error,
    'aria-describedby': error ? `${name}-error` : undefined,
  };
}

function FieldError(props: FieldErrorProps) {
  const { name, error } = props;
  if (!error) return null;
  return (
    <p id={`${name}-error`} className="text-sm text-red-500 flex items-center gap-1">
      <AlertCircle className="w-4 h-4" />
      {error}
    </p>
  );
}

function FieldLabel(props: FieldLabelProps) {
  const { name, label, required } = props;
  return (
    <Label htmlFor={name} className="flex items-center gap-1">
      {label}
      {required ? <span className="text-red-500">*</span> : null}
    </Label>
  );
}

// Multi-select dropdown for an array of strings (typically column selection).
function MultiSelectField(props: FieldProps) {
  const { name, field, value, error, availableColumns, onChange } = props;
  const handleChange = (selected: string[]) => onChange(name, selected);
  return (
    <div className="grid gap-2">
      <FieldLabel name={name} label={fieldLabel(name, field)} required={isRequired(field)} />
      <MultiSelect
        id={name}
        options={availableColumns}
        value={Array.isArray(value) ? value : []}
        onChange={handleChange}
        placeholder={field.description || 'Select columns...'}
        error={error}
        {...errorAria(name, error)}
      />
      <FieldError name={name} error={error} />
    </div>
  );
}

// Single select for enum values, or for a string field about columns.
function SelectField(props: FieldProps) {
  const { name, field, value, error, availableColumns, onChange } = props;
  const handleValueChange = (selectedValue: string) => onChange(name, selectedValue);
  return (
    <div className="grid gap-2">
      <FieldLabel name={name} label={fieldLabel(name, field)} required={isRequired(field)} />
      <Select value={value} onValueChange={handleValueChange}>
        <SelectTrigger id={name} {...errorAria(name, error)}>
          <SelectValue placeholder={field.description || 'Select an option'} />
        </SelectTrigger>
        <SelectContent>
          {selectOptions(field, availableColumns).map((option) => (
            <SelectItem key={option} value={option}>
              {optionLabel(option)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <FieldError name={name} error={error} />
    </div>
  );
}

function NumberField(props: FieldProps) {
  const { name, field, value, error, inputRef, onChange } = props;
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) =>
    onChange(name, e.target.value ? Number(e.target.value) : '');
  return (
    <div className="grid gap-2">
      <FieldLabel name={name} label={fieldLabel(name, field)} required={isRequired(field)} />
      <Input
        ref={inputRef}
        id={name}
        type="number"
        value={value}
        onChange={handleChange}
        placeholder={field.description || 'Enter a number'}
        step={field.type === 'integer' ? '1' : 'any'}
        min={field.minimum}
        max={field.maximum}
        {...errorAria(name, error)}
      />
      <FieldError name={name} error={error} />
    </div>
  );
}

function BooleanField(props: FieldProps) {
  const { name, field, value, error, inputRef, onChange } = props;
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => onChange(name, e.target.checked);
  return (
    <div className="grid gap-2">
      <div className="flex items-center gap-2">
        <input
          ref={inputRef}
          id={name}
          type="checkbox"
          checked={!!value}
          onChange={handleChange}
          className="w-4 h-4 rounded border border-input"
          {...errorAria(name, error)}
        />
        <Label htmlFor={name} className="flex items-center gap-1 cursor-pointer">
          {fieldLabel(name, field)}
        </Label>
      </div>
      <FieldError name={name} error={error} />
    </div>
  );
}

// Text input, also for string fields and for types the form does not know.
function TextField(props: FieldProps) {
  const { name, field, value, error, inputRef, onChange } = props;
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => onChange(name, e.target.value);
  return (
    <div className="grid gap-2">
      <FieldLabel name={name} label={fieldLabel(name, field)} required={isRequired(field)} />
      <Input
        ref={inputRef}
        id={name}
        type="text"
        value={value}
        onChange={handleChange}
        placeholder={field.description || 'Enter value'}
        {...errorAria(name, error)}
      />
      <FieldError name={name} error={error} />
    </div>
  );
}

const FIELD_COMPONENTS: Record<FieldKind, ComponentType<FieldProps>> = {
  multi: MultiSelectField,
  select: SelectField,
  number: NumberField,
  boolean: BooleanField,
  text: TextField,
};

interface ParameterFieldProps {
  name: string;
  schema: ParametersSchema;
  parameters: Record<string, unknown>;
  errors: Record<string, string>;
  availableColumns: string[];
  firstInputRef: MutableRefObject<HTMLInputElement | null>;
  onChange(key: string, value: unknown): void;
}

// The first field's input is where focus lands on open and where Shift+Tab wraps.
function captureFirstInput(
  firstInputRef: MutableRefObject<HTMLInputElement | null>,
  schema: ParametersSchema,
  name: string
) {
  return (el: HTMLInputElement | null) => {
    if (!firstInputRef.current && name === Object.keys(schema)[0]) {
      firstInputRef.current = el;
    }
  };
}

function ParameterField(props: ParameterFieldProps) {
  const { name, schema, parameters, errors, availableColumns, firstInputRef, onChange } = props;
  const field = schema[name];
  const Field = FIELD_COMPONENTS[fieldKind(name, field, availableColumns)];
  return (
    <Field
      name={name}
      field={field}
      value={parameters[name] ?? ''}
      error={errors[name]}
      availableColumns={availableColumns}
      inputRef={captureFirstInput(firstInputRef, schema, name)}
      onChange={onChange}
    />
  );
}

interface ParameterFormProps {
  schema: ParametersSchema;
  parameters: Record<string, unknown>;
  errors: Record<string, string>;
  availableColumns: string[];
  firstInputRef: MutableRefObject<HTMLInputElement | null>;
  onChange(key: string, value: unknown): void;
}

function ParameterForm(props: ParameterFormProps) {
  const { schema, ...rest } = props;
  const names = Object.keys(schema);
  const renderField = (name: string) => (
    <ParameterField key={name} name={name} schema={schema} {...rest} />
  );
  if (names.length === 0) {
    return <p className="text-sm text-muted-foreground">No parameters needed for this transformation.</p>;
  }
  return <>{names.map(renderField)}</>;
}

function ErrorBanner(props: { message: string | undefined }) {
  const { message } = props;
  if (!message) return null;
  return (
    <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 rounded-md flex items-start gap-2">
      <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
      <p className="text-sm text-red-700 dark:text-red-300">{message}</p>
    </div>
  );
}

interface DialogActionsProps {
  isBusy: boolean;
  isUpdate: boolean;
  lastInteractiveRef: RefObject<HTMLButtonElement | null>;
  onDelete?: VoidFunction;
  onPreview?: VoidFunction;
  onAdd: VoidFunction;
}

interface ActionButtonProps {
  isBusy: boolean;
  onClick: VoidFunction;
}

interface DeleteButtonProps extends ActionButtonProps {
  buttonRef: RefObject<HTMLButtonElement | null>;
}

function DeleteButton(props: DeleteButtonProps) {
  const { isBusy, onClick, buttonRef } = props;
  return (
    <Button
      ref={buttonRef}
      variant="destructive"
      size="sm"
      onClick={onClick}
      disabled={isBusy}
      aria-label="Delete this transformation"
    >
      <Trash2 className="mr-2 h-4 w-4" />
      Delete
    </Button>
  );
}

function PreviewButton(props: ActionButtonProps) {
  const { isBusy, onClick } = props;
  return (
    <Button
      variant="outline"
      onClick={onClick}
      disabled={isBusy}
      aria-label="Preview transformation effect"
    >
      <Eye className="mr-2 h-4 w-4" />
      Preview
    </Button>
  );
}

function DialogActions(props: DialogActionsProps) {
  const { isBusy, isUpdate, lastInteractiveRef, onDelete, onPreview, onAdd } = props;
  return (
    <DialogFooter className="flex gap-2">
      {onDelete ? <DeleteButton isBusy={isBusy} onClick={onDelete} buttonRef={lastInteractiveRef} /> : null}

      <div className="flex-1" />

      {onPreview ? <PreviewButton isBusy={isBusy} onClick={onPreview} /> : null}

      <Button
        ref={!onDelete ? lastInteractiveRef : undefined}
        variant="default"
        onClick={onAdd}
        disabled={isBusy}
        aria-label="Add transformation to pipeline"
      >
        <Plus className="mr-2 h-4 w-4" />
        {isUpdate ? 'Update' : 'Add'} to Pipeline
      </Button>
    </DialogFooter>
  );
}

/**
 * TransformationConfigDialog
 *
 * Modal dialog for configuring transformation parameters with dynamic form rendering.
 * Supports multiple parameter types (string, number, boolean, array, enum) with validation.
 * Includes keyboard navigation, focus trap, and accessibility features.
 *
 * Features:
 * - Dynamic form generation based on transformation parameter schema
 * - Column selection dropdown for applicable transformations
 * - Parameter validation before adding to pipeline (values are checked, never converted)
 * - Preview button to test transformation (optional)
 * - Focus trap while dialog is open
 * - Keyboard navigation (Tab, Escape, Enter)
 * - ARIA labels and accessibility attributes
 */
export function TransformationConfigDialog(props: TransformationConfigDialogProps) {
  const {
    open,
    onOpenChange,
    transformationLabel,
    transformationDescription,
    parametersSchema,
    availableColumns,
    onPreview,
    existingConfig,
    onDelete,
  } = props;
  const form = useTransformationForm(props);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[500px]"
        onKeyDown={form.handleKeyDown}
        role="dialog"
        aria-labelledby="transform-dialog-title"
        aria-describedby="transform-dialog-desc"
      >
        <DialogHeader>
          <DialogTitle id="transform-dialog-title">
            {transformationLabel}
          </DialogTitle>
          <DialogDescription id="transform-dialog-desc">
            {transformationDescription}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4" role="group">
          <ParameterForm
            schema={parametersSchema}
            parameters={form.parameters}
            errors={form.errors}
            availableColumns={availableColumns}
            firstInputRef={form.firstInputRef}
            onChange={form.handleParameterChange}
          />
          <ErrorBanner message={form.errors._preview} />
          <ErrorBanner message={form.errors._submit} />
        </div>

        <DialogActions
          isBusy={form.isBusy}
          isUpdate={!!existingConfig}
          lastInteractiveRef={form.lastInteractiveRef}
          onDelete={onDelete}
          onPreview={onPreview ? form.handlePreview : undefined}
          onAdd={form.handleAdd}
        />
      </DialogContent>
    </Dialog>
  );
}

