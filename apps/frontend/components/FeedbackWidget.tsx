'use client';

/**
 * Floating feedback widget (issue #152, AC3).
 *
 * A bottom-right button that expands into a short form (star rating, category,
 * message) and POSTs to `/api/v1/feedback`. Uses inline success/error states
 * rather than a global toast system (none exists in the app yet).
 */

import React, { useEffect, useRef, useState } from 'react';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { MessageSquarePlus, Star, X, CheckCircle, Loader2 } from 'lucide-react';

const CATEGORIES = [
  { value: 'general', label: 'General feedback' },
  { value: 'bug', label: 'Report a bug' },
  { value: 'feature_request', label: 'Request a feature' },
  { value: 'onboarding', label: 'Onboarding' },
] as const;

export function FeedbackWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [rating, setRating] = useState(0);
  const [category, setCategory] = useState<string>('general');
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  // Set when the dialog closes so focus returns to the opener on the next render
  // rather than being dropped to <body> (WCAG 2.4.3 / issue #282).
  const restoreFocusRef = useRef(false);

  const focusableSelector =
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  // On open, move focus into the dialog; on close, return it to the trigger.
  useEffect(() => {
    if (isOpen) {
      panelRef.current?.querySelector<HTMLElement>(focusableSelector)?.focus();
    } else if (restoreFocusRef.current) {
      triggerRef.current?.focus();
      restoreFocusRef.current = false;
    }
  }, [isOpen]);

  // Escape closes; Tab is trapped within the dialog so focus can't leak out.
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      close();
      return;
    }
    if (e.key !== 'Tab' || !panelRef.current) return;
    const nodes = Array.from(
      panelRef.current.querySelectorAll<HTMLElement>(focusableSelector)
    );
    if (nodes.length === 0) return;
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  const resetForm = () => {
    setRating(0);
    setCategory('general');
    setMessage('');
    setStatus('idle');
    setErrorMessage(null);
  };

  const close = () => {
    restoreFocusRef.current = true;
    setIsOpen(false);
    resetForm();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (rating < 1) {
      setStatus('error');
      setErrorMessage('Please select a star rating.');
      return;
    }
    if (message.trim().length === 0) {
      setStatus('error');
      setErrorMessage('Please enter a message.');
      return;
    }

    // Abort a stalled request so the widget never gets stuck on "Sending…".
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      setStatus('submitting');
      const token = await getAuthToken();
      const response = await fetch(`${API_URL}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          rating,
          category,
          message: message.trim(),
          page_context:
            typeof window !== 'undefined' ? window.location.pathname : null,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Submission failed (${response.status})`);
      }

      setStatus('success');
    } catch (err) {
      setStatus('error');
      const isAbort = err instanceof DOMException && err.name === 'AbortError';
      setErrorMessage(
        isAbort
          ? 'The request timed out. Please try again.'
          : err instanceof Error
            ? err.message
            : 'Something went wrong. Please try again.'
      );
    } finally {
      clearTimeout(timeout);
    }
  };

  if (!isOpen) {
    return (
      <Button
        ref={triggerRef}
        type="button"
        onClick={() => setIsOpen(true)}
        data-testid="feedback-widget-button"
        aria-label="Give feedback"
        className="fixed bottom-6 right-6 z-50 rounded-full shadow-lg gap-2"
      >
        <MessageSquarePlus className="h-4 w-4" />
        Feedback
      </Button>
    );
  }

  return (
    <div
      ref={panelRef}
      role="dialog"
      aria-modal="true"
      aria-label="Feedback form"
      data-testid="feedback-widget-panel"
      onKeyDown={handleKeyDown}
      className="fixed bottom-6 right-6 z-50 w-80 rounded-lg border bg-white shadow-xl"
    >
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h2 className="font-semibold text-gray-900">Share your feedback</h2>
        <button
          type="button"
          onClick={close}
          aria-label="Close feedback form"
          className="text-gray-500 hover:text-gray-800"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {status === 'success' ? (
        <div className="p-4 text-center" data-testid="feedback-success">
          <CheckCircle className="mx-auto h-10 w-10 text-green-600" />
          <p className="mt-2 font-medium text-gray-900">Thanks for your feedback!</p>
          <div className="mt-4 flex justify-center gap-2">
            <Button type="button" variant="outline" size="sm" onClick={resetForm}>
              Send another
            </Button>
            <Button type="button" size="sm" onClick={close}>
              Done
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-3 p-4">
          <div>
            <span className="mb-1 block text-sm font-medium text-gray-700">
              How would you rate your experience?
            </span>
            <div className="flex gap-1" role="group" aria-label="Star rating">
              {[1, 2, 3, 4, 5].map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setRating(value)}
                  aria-label={`Rate ${value} star${value === 1 ? '' : 's'}`}
                  aria-pressed={rating >= value}
                  data-testid={`feedback-star-${value}`}
                  className="text-gray-300 hover:text-yellow-400"
                >
                  <Star
                    className={`h-6 w-6 ${
                      rating >= value ? 'fill-yellow-400 text-yellow-400' : ''
                    }`}
                  />
                </button>
              ))}
            </div>
          </div>

          <div>
            <label
              htmlFor="feedback-category"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Category
            </label>
            <select
              id="feedback-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              data-testid="feedback-category"
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="feedback-message"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Your feedback
            </label>
            <Textarea
              id="feedback-message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Tell us what's working or what could be better…"
              rows={4}
              data-testid="feedback-message"
              maxLength={2000}
            />
          </div>

          {status === 'error' && errorMessage && (
            <p
              className="text-sm text-red-600"
              role="alert"
              data-testid="feedback-error"
            >
              {errorMessage}
            </p>
          )}

          <Button
            type="submit"
            disabled={status === 'submitting'}
            data-testid="feedback-submit"
            className="w-full gap-2"
          >
            {status === 'submitting' && <Loader2 className="h-4 w-4 animate-spin" />}
            {status === 'submitting' ? 'Sending…' : 'Send feedback'}
          </Button>
        </form>
      )}
    </div>
  );
}

export default FeedbackWidget;
