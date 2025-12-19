/**
 * Async Testing Helpers
 *
 * Utilities for handling async operations in tests with proper act() wrapping
 * to eliminate React 18 act() warnings.
 */

import { waitFor as waitForBase, waitForOptions } from '@testing-library/react';
import { act } from '@testing-library/react';

/**
 * Wrapper around waitFor that automatically wraps in act()
 * Use this instead of waitFor() + getBy* queries
 *
 * @example
 * // Instead of:
 * await waitFor(() => {
 *   expect(screen.getByText('Loading')).toBeInTheDocument();
 * });
 *
 * // Use:
 * await waitForAsync(() => {
 *   expect(screen.getByText('Loading')).toBeInTheDocument();
 * });
 */
export async function waitForAsync(
  callback: () => void | Promise<void>,
  options: waitForOptions = {}
): Promise<void> {
  return act(async () => {
    await waitForBase(callback, {
      timeout: 3000,
      interval: 50,
      ...options,
    });
  });
}

/**
 * Wait for an element to appear in the document
 * Combines findBy* semantics with explicit act() wrapping
 *
 * @example
 * await waitForElement(() => screen.getByText('Success'));
 */
export async function waitForElement(
  queryFn: () => HTMLElement,
  options: waitForOptions = {}
): Promise<HTMLElement> {
  let element: HTMLElement | null = null;

  await act(async () => {
    await waitForBase(() => {
      element = queryFn();
      expect(element).toBeInTheDocument();
    }, {
      timeout: 3000,
      interval: 50,
      ...options,
    });
  });

  return element!;
}

/**
 * Wait for an element to be removed from the document
 *
 * @example
 * await waitForElementToBeRemoved(() => screen.queryByText('Loading'));
 */
export async function waitForElementToBeRemoved(
  queryFn: () => HTMLElement | null,
  options: waitForOptions = {}
): Promise<void> {
  return act(async () => {
    await waitForBase(() => {
      expect(queryFn()).not.toBeInTheDocument();
    }, {
      timeout: 3000,
      interval: 50,
      ...options,
    });
  });
}

/**
 * Wrapper for async user interactions that trigger state updates
 * Use this when fireEvent or userEvent causes state changes
 *
 * @example
 * await actAsync(async () => {
 *   fireEvent.click(button);
 * });
 */
export async function actAsync(
  callback: () => void | Promise<void>
): Promise<void> {
  await act(async () => {
    await callback();
  });
}

/**
 * Wait for async state updates to complete
 * Useful after triggering actions that update state asynchronously
 *
 * @example
 * fireEvent.click(button);
 * await waitForStateUpdate();
 * expect(screen.getByText('Updated')).toBeInTheDocument();
 */
export async function waitForStateUpdate(ms: number = 0): Promise<void> {
  await act(async () => {
    await new Promise(resolve => setTimeout(resolve, ms));
  });
}

/**
 * Helper to wait for multiple conditions to be true
 * All conditions must pass within the timeout period
 *
 * @example
 * await waitForAll([
 *   () => expect(screen.getByText('Title')).toBeInTheDocument(),
 *   () => expect(screen.getByRole('button')).toBeEnabled(),
 * ]);
 */
export async function waitForAll(
  conditions: Array<() => void>,
  options: waitForOptions = {}
): Promise<void> {
  return act(async () => {
    await waitForBase(() => {
      conditions.forEach(condition => condition());
    }, {
      timeout: 3000,
      interval: 50,
      ...options,
    });
  });
}

/**
 * Type guard to check if an element exists
 * Useful with TypeScript strict mode
 */
export function assertElementExists(
  element: HTMLElement | null
): asserts element is HTMLElement {
  expect(element).toBeInTheDocument();
}
