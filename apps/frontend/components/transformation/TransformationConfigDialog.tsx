'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
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

interface TransformationConfigDialogProps {
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

export interface TransformationConfig {
  type: string;
  parameters: Record<string, any>;
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
 * - Parameter validation before adding to pipeline
 * - Preview button to test transformation (optional)
 * - Focus trap while dialog is open
 * - Keyboard navigation (Tab, Escape, Enter)
 * - ARIA labels and accessibility attributes
 */
export function TransformationConfigDialog({
  open,
  onOpenChange,
  transformationType,
  transformationLabel,
  transformationDescription,
  parametersSchema,
  availableColumns,
  datasetId,
  onAdd,
  onPreview,
  existingConfig,
  onDelete,
}: TransformationConfigDialogProps) {
  const [parameters, setParameters] = useState<Record<string, any>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const firstInputRef = useRef<HTMLInputElement | null>(null);
  const lastInteractiveRef = useRef<HTMLButtonElement | null>(null);

  // Reset form when dialog opens/closes or transformation changes
  useEffect(() => {
    if (open) {
      if (existingConfig?.parameters) {
        setParameters({ ...existingConfig.parameters });
      } else {
        setParameters({});
      }
      setErrors({});
      // Focus first input after dialog is rendered
      setTimeout(() => {
        firstInputRef.current?.focus();
      }, 0);
    }
  }, [open, transformationType, existingConfig]);

  /**
   * Handle parameter value changes with error clearing
   */
  const handleParameterChange = useCallback(
    (key: string, value: any) => {
      setParameters((prev) => ({ ...prev, [key]: value }));
      // Clear error for this field
      if (errors[key]) {
        setErrors((prev) => {
          const newErrors = { ...prev };
          delete newErrors[key];
          return newErrors;
        });
      }
    },
    [errors]
  );

  /**
   * Validate form parameters based on schema requirements
   */
  const validateForm = useCallback((): boolean => {
    const newErrors: Record<string, string> = {};

    Object.entries(parametersSchema).forEach(([key, schema]) => {
      const value = parameters[key];

      // Check if field is required (not marked as optional in schema)
      if (schema.required !== false && !schema.default) {
        if (
          value === undefined ||
          value === null ||
          value === '' ||
          (Array.isArray(value) && value.length === 0)
        ) {
          newErrors[key] = `${formatFieldName(key)} is required`;
          return;
        }
      }

      // Type validation
      if (value !== undefined && value !== null && value !== '') {
        if (schema.type === 'array' && !Array.isArray(value)) {
          newErrors[key] = `${formatFieldName(key)} must be an array`;
        } else if (schema.type === 'number' && typeof value !== 'number') {
          // Try to coerce string to number
          if (typeof value === 'string' && value === '') {
            if (schema.required !== false) {
              newErrors[key] = `${formatFieldName(key)} is required`;
            }
          } else if (isNaN(Number(value))) {
            newErrors[key] = `${formatFieldName(key)} must be a number`;
          }
        } else if (
          schema.type === 'string' &&
          typeof value !== 'string'
        ) {
          newErrors[key] = `${formatFieldName(key)} must be text`;
        }

        // Enum validation
        if (schema.enum && !schema.enum.includes(value)) {
          newErrors[key] = `${formatFieldName(key)} must be one of: ${schema.enum.join(', ')}`;
        }

        // Minimum/maximum validation
        if (
          schema.type === 'number' &&
          typeof value === 'number'
        ) {
          if (schema.minimum !== undefined && value < schema.minimum) {
            newErrors[key] = `${formatFieldName(key)} must be at least ${schema.minimum}`;
          }
          if (schema.maximum !== undefined && value > schema.maximum) {
            newErrors[key] = `${formatFieldName(key)} must be no more than ${schema.maximum}`;
          }
        }
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [parameters, parametersSchema]);

  /**
   * Format schema key to human-readable field name
   */
  const formatFieldName = (key: string): string => {
    return key
      .replace(/_/g, ' ')
      .replace(/([A-Z])/g, ' $1')
      .trim()
      .split(' ')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  /**
   * Handle preview transformation
   */
  const handlePreview = async () => {
    if (!validateForm()) return;
    if (!onPreview || !transformationType) return;

    setIsPreviewLoading(true);
    try {
      await onPreview({
        type: transformationType,
        parameters,
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Preview failed';
      setErrors((prev) => ({ ...prev, _preview: message }));
    } finally {
      setIsPreviewLoading(false);
    }
  };

  /**
   * Handle form submission
   */
  const handleAdd = async () => {
    if (!validateForm()) return;
    if (!transformationType) return;

    setIsSubmitting(true);
    try {
      onAdd({
        type: transformationType,
        parameters,
      });
      onOpenChange(false);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to add transformation';
      setErrors((prev) => ({ ...prev, _submit: message }));
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Render form field based on schema definition
   */
  const renderFormField = (key: string, schema: any) => {
    const value = parameters[key] ?? '';
    const error = errors[key];
    const fieldLabel = schema.title || formatFieldName(key);
    const isRequired = schema.required !== false && !schema.default;

    // Multi-select dropdown for array of strings (typically column selection)
    if (
      schema.type === 'array' &&
      schema.items?.type === 'string'
    ) {
      return (
        <div key={key} className="grid gap-2">
          <Label htmlFor={key} className="flex items-center gap-1">
            {fieldLabel}
            {isRequired && <span className="text-red-500">*</span>}
          </Label>
          <MultiSelect
            id={key}
            options={availableColumns}
            value={Array.isArray(value) ? value : []}
            onChange={(selected) => handleParameterChange(key, selected)}
            placeholder={schema.description || 'Select columns...'}
            error={error}
            aria-invalid={!!error}
            aria-describedby={error ? `${key}-error` : undefined}
          />
          {error && (
            <p id={`${key}-error`} className="text-sm text-red-500 flex items-center gap-1">
              <AlertCircle className="w-4 h-4" />
              {error}
            </p>
          )}
        </div>
      );
    }

    // Single select dropdown (enum values)
    if (schema.enum) {
      return (
        <div key={key} className="grid gap-2">
          <Label htmlFor={key} className="flex items-center gap-1">
            {fieldLabel}
            {isRequired && <span className="text-red-500">*</span>}
          </Label>
          <Select
            value={value}
            onValueChange={(selectedValue) =>
              handleParameterChange(key, selectedValue)
            }
          >
            <SelectTrigger
              id={key}
              aria-invalid={!!error}
              aria-describedby={error ? `${key}-error` : undefined}
            >
              <SelectValue placeholder={schema.description || 'Select an option'} />
            </SelectTrigger>
            <SelectContent>
              {schema.enum.map((option: string) => (
                <SelectItem key={option} value={option}>
                  {option
                    .split('_')
                    .map(
                      (word: string) =>
                        word.charAt(0).toUpperCase() + word.slice(1)
                    )
                    .join(' ')}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {error && (
            <p id={`${key}-error`} className="text-sm text-red-500 flex items-center gap-1">
              <AlertCircle className="w-4 h-4" />
              {error}
            </p>
          )}
        </div>
      );
    }

    // Number input
    if (schema.type === 'number' || schema.type === 'integer') {
      return (
        <div key={key} className="grid gap-2">
          <Label htmlFor={key} className="flex items-center gap-1">
            {fieldLabel}
            {isRequired && <span className="text-red-500">*</span>}
          </Label>
          <Input
            ref={(el) => {
              if (!firstInputRef.current && key === Object.keys(parametersSchema)[0]) {
                firstInputRef.current = el;
              }
            }}
            id={key}
            type="number"
            value={value}
            onChange={(e) => handleParameterChange(key, e.target.value ? Number(e.target.value) : '')}
            placeholder={schema.description || 'Enter a number'}
            step={schema.type === 'integer' ? '1' : 'any'}
            min={schema.minimum}
            max={schema.maximum}
            aria-invalid={!!error}
            aria-describedby={error ? `${key}-error` : undefined}
          />
          {error && (
            <p id={`${key}-error`} className="text-sm text-red-500 flex items-center gap-1">
              <AlertCircle className="w-4 h-4" />
              {error}
            </p>
          )}
        </div>
      );
    }

    // Boolean checkbox
    if (schema.type === 'boolean') {
      return (
        <div key={key} className="grid gap-2">
          <div className="flex items-center gap-2">
            <input
              ref={(el) => {
                if (!firstInputRef.current && key === Object.keys(parametersSchema)[0]) {
                  firstInputRef.current = el;
                }
              }}
              id={key}
              type="checkbox"
              checked={!!value}
              onChange={(e) => handleParameterChange(key, e.target.checked)}
              className="w-4 h-4 rounded border border-input"
              aria-invalid={!!error}
              aria-describedby={error ? `${key}-error` : undefined}
            />
            <Label htmlFor={key} className="flex items-center gap-1 cursor-pointer">
              {fieldLabel}
            </Label>
          </div>
          {error && (
            <p id={`${key}-error`} className="text-sm text-red-500 flex items-center gap-1">
              <AlertCircle className="w-4 h-4" />
              {error}
            </p>
          )}
        </div>
      );
    }

    // Default: text input (for string type or unknown types)
    return (
      <div key={key} className="grid gap-2">
        <Label htmlFor={key} className="flex items-center gap-1">
          {fieldLabel}
          {isRequired && <span className="text-red-500">*</span>}
        </Label>
        <Input
          ref={(el) => {
            if (!firstInputRef.current && key === Object.keys(parametersSchema)[0]) {
              firstInputRef.current = el;
            }
          }}
          id={key}
          type="text"
          value={value}
          onChange={(e) => handleParameterChange(key, e.target.value)}
          placeholder={schema.description || 'Enter value'}
          aria-invalid={!!error}
          aria-describedby={error ? `${key}-error` : undefined}
        />
        {error && (
          <p id={`${key}-error`} className="text-sm text-red-500 flex items-center gap-1">
            <AlertCircle className="w-4 h-4" />
            {error}
          </p>
        )}
      </div>
    );
  };

  /**
   * Handle keyboard events (Escape to close, focus trap)
   */
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        onOpenChange(false);
      }
      // Focus trap on Tab
      if (e.key === 'Tab' && lastInteractiveRef.current) {
        if (e.shiftKey && document.activeElement === firstInputRef.current) {
          e.preventDefault();
          lastInteractiveRef.current.focus();
        } else if (!e.shiftKey && document.activeElement === lastInteractiveRef.current) {
          e.preventDefault();
          firstInputRef.current?.focus();
        }
      }
    },
    [onOpenChange]
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[500px]"
        onKeyDown={handleKeyDown}
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
          {Object.keys(parametersSchema).length > 0 ? (
            Object.entries(parametersSchema).map(([key, schema]) =>
              renderFormField(key, schema)
            )
          ) : (
            <p className="text-sm text-gray-600">
              No parameters needed for this transformation.
            </p>
          )}

          {errors._preview && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">{errors._preview}</p>
            </div>
          )}

          {errors._submit && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">{errors._submit}</p>
            </div>
          )}
        </div>

        <DialogFooter className="flex gap-2">
          {onDelete && (
            <Button
              ref={lastInteractiveRef}
              variant="destructive"
              size="sm"
              onClick={onDelete}
              disabled={isSubmitting || isPreviewLoading}
              aria-label="Delete this transformation"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </Button>
          )}

          <div className="flex-1" />

          {onPreview && (
            <Button
              variant="outline"
              onClick={handlePreview}
              disabled={isSubmitting || isPreviewLoading}
              loading={isPreviewLoading}
              aria-label="Preview transformation effect"
            >
              <Eye className="mr-2 h-4 w-4" />
              Preview
            </Button>
          )}

          <Button
            ref={!onDelete ? lastInteractiveRef : undefined}
            variant="default"
            onClick={handleAdd}
            disabled={isSubmitting || isPreviewLoading}
            loading={isSubmitting}
            aria-label="Add transformation to pipeline"
          >
            <Plus className="mr-2 h-4 w-4" />
            {existingConfig ? 'Update' : 'Add'} to Pipeline
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * MultiSelect component for selecting multiple columns
 * Supports keyboard navigation and search filtering
 */
interface MultiSelectProps {
  id: string;
  options: string[];
  value: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
  error?: string;
  'aria-invalid'?: boolean;
  'aria-describedby'?: string;
}

function MultiSelect({
  id,
  options,
  value,
  onChange,
  placeholder = 'Select items...',
  error,
}: MultiSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const triggerRef = useRef<HTMLButtonElement>(null);

  const filteredOptions = options.filter((option) =>
    option.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleSelect = (option: string) => {
    if (value.includes(option)) {
      onChange(value.filter((v) => v !== option));
    } else {
      onChange([...value, option]);
    }
  };

  const handleSelectAll = () => {
    if (value.length === filteredOptions.length) {
      onChange([]);
    } else {
      const newValue = [
        ...value,
        ...filteredOptions.filter((v) => !value.includes(v)),
      ];
      onChange(newValue);
    }
  };

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full h-9 px-3 py-1 text-sm text-left border rounded-md bg-transparent transition-colors
          ${error ? 'border-red-500' : 'border-input'}
          focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring
        `}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={`${id}-listbox`}
      >
        <div className="flex items-center justify-between">
          <span className={value.length > 0 ? 'text-foreground' : 'text-muted-foreground'}>
            {value.length > 0
              ? `${value.length} selected`
              : placeholder}
          </span>
          <span className="text-xs text-muted-foreground">▼</span>
        </div>
      </button>

      {isOpen && (
        <>
          <div
            className="absolute top-0 left-0 right-0 bottom-0"
            onClick={() => setIsOpen(false)}
          />
          <div
            className="absolute top-full left-0 right-0 mt-1 bg-background border rounded-md shadow-lg z-50 max-h-64 overflow-y-auto"
            role="listbox"
            id={`${id}-listbox`}
            aria-multiselectable="true"
          >
            <div className="p-2 border-b sticky top-0 bg-background">
              <input
                type="text"
                placeholder="Search..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full h-8 px-2 text-sm border rounded"
                aria-label="Search columns"
              />
            </div>

            <div className="p-2">
              <button
                type="button"
                onClick={handleSelectAll}
                className="w-full p-2 text-sm text-left hover:bg-accent rounded transition-colors mb-1"
              >
                <span className="font-medium">
                  {value.length === filteredOptions.length ? 'Deselect' : 'Select'} All
                </span>
              </button>
            </div>

            <div className="border-t">
              {filteredOptions.map((option) => (
                <label
                  key={option}
                  className="flex items-center gap-2 p-2 hover:bg-accent cursor-pointer transition-colors"
                  role="option"
                  aria-selected={value.includes(option)}
                >
                  <input
                    type="checkbox"
                    checked={value.includes(option)}
                    onChange={() => handleSelect(option)}
                    className="w-4 h-4 rounded border border-input"
                  />
                  <span className="text-sm">{option}</span>
                </label>
              ))}
            </div>

            {filteredOptions.length === 0 && (
              <div className="p-4 text-sm text-center text-muted-foreground">
                No columns found
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
