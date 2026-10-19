import { useState, useEffect, useRef, useCallback } from 'react';
import type { KeyboardEvent } from 'react';
import { validateParameters, type ParametersSchema } from './parameterSchema';

export interface TransformationConfig {
  type: string;
  label?: string;
  parameters: Record<string, any>;
}

export interface TransformationFormArgs {
  open: boolean;
  onOpenChange(open: boolean): void;
  transformationType: string | null;
  existingConfig?: TransformationConfig | null;
  parametersSchema: ParametersSchema;
  onAdd(config: TransformationConfig): void;
  onPreview?: (config: TransformationConfig) => Promise<void>;
}

interface FormSubject {
  open: boolean;
  transformationType: string | null;
  existingConfig?: TransformationConfig | null;
}

function subjectChanged(before: FormSubject, after: FormSubject): boolean {
  return (
    before.open !== after.open ||
    before.transformationType !== after.transformationType ||
    before.existingConfig !== after.existingConfig
  );
}

function seedParameters(existingConfig?: TransformationConfig | null): Record<string, unknown> {
  return existingConfig?.parameters ? { ...existingConfig.parameters } : {};
}

export function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function withoutKey(errors: Record<string, string>, key: string): Record<string, string> {
  const rest = { ...errors };
  delete rest[key];
  return rest;
}

// Which element Tab (or Shift+Tab) leaves from, and where focus wraps to.
function focusEdges(
  shiftKey: boolean,
  first: HTMLElement | null,
  last: HTMLElement
): [HTMLElement | null, HTMLElement | null] {
  return shiftKey ? [first, last] : [last, first];
}

function trapFocus(
  event: KeyboardEvent,
  first: HTMLElement | null,
  last: HTMLElement | null
): void {
  if (event.key !== 'Tab' || !last) return;
  const [from, to] = focusEdges(event.shiftKey, first, last);
  if (document.activeElement !== from) return;
  event.preventDefault();
  to?.focus();
}

/**
 * Form state for the transformation dialog: the entered parameters, their
 * validation errors, the add / preview actions and the focus trap.
 */
export function useTransformationForm(args: TransformationFormArgs) {
  const { open, onOpenChange, transformationType, existingConfig, parametersSchema, onAdd, onPreview } = args;
  const [parameters, setParameters] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const firstInputRef = useRef<HTMLInputElement | null>(null);
  const lastInteractiveRef = useRef<HTMLButtonElement | null>(null);

  // Resetting form state when the dialog opens (or its subject changes) is a
  // prop-driven reset, so it happens during render rather than in an effect.
  const subject = { open, transformationType, existingConfig };
  const [formSubject, setFormSubject] = useState(subject);
  if (subjectChanged(formSubject, subject)) {
    setFormSubject(subject);
    if (open) {
      setParameters(seedParameters(existingConfig));
      setErrors({});
    }
  }

  // The focus call is a real DOM side effect and stays an effect.
  useEffect(() => {
    if (!open) return;
    const timeoutId = setTimeout(() => {
      firstInputRef.current?.focus();
    }, 0);
    return () => clearTimeout(timeoutId);
  }, [open, transformationType, existingConfig]);

  const setFormError = (key: string, message: string) =>
    setErrors((prev) => ({ ...prev, [key]: message }));

  const handleParameterChange = useCallback(
    (key: string, value: unknown) => {
      setParameters((prev) => ({ ...prev, [key]: value }));
      if (errors[key]) setErrors((prev) => withoutKey(prev, key));
    },
    [errors]
  );

  const validateForm = useCallback((): boolean => {
    const newErrors = validateParameters(parametersSchema, parameters);
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [parameters, parametersSchema]);

  const handlePreview = async () => {
    if (!validateForm() || !onPreview || !transformationType) return;
    setIsPreviewLoading(true);
    try {
      await onPreview({ type: transformationType, parameters });
    } catch (error) {
      setFormError('_preview', errorMessage(error, 'Preview failed'));
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const handleAdd = async () => {
    if (!validateForm() || !transformationType) return;
    setIsSubmitting(true);
    try {
      onAdd({ type: transformationType, parameters });
      onOpenChange(false);
    } catch (error) {
      setFormError('_submit', errorMessage(error, 'Failed to add transformation'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') onOpenChange(false);
    trapFocus(event, firstInputRef.current, lastInteractiveRef.current);
  };

  return {
    parameters,
    errors,
    isBusy: isSubmitting || isPreviewLoading,
    firstInputRef,
    lastInteractiveRef,
    handleParameterChange,
    handlePreview,
    handleAdd,
    handleKeyDown,
  };
}
