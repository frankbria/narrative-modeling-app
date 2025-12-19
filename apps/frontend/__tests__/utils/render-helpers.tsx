/**
 * Render Helpers
 *
 * Custom render utilities for testing components with providers and contexts
 */

import React, { ReactElement } from 'react';
import { render, RenderOptions, RenderResult } from '@testing-library/react';

/**
 * Options for customizing the render wrapper
 */
export interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  /**
   * Initial route for Next.js router mock
   */
  initialRoute?: string;

  /**
   * Initial dataset ID for WorkflowProvider
   */
  initialDatasetId?: string;

  /**
   * Additional wrapper components to wrap around the component under test
   */
  wrapper?: React.ComponentType<{ children: React.ReactNode }>;

  /**
   * Whether to wrap with WorkflowProvider (default: false)
   */
  withWorkflow?: boolean;
}

/**
 * Mock Next.js router for testing
 */
export function mockRouter(overrides: Partial<{
  push: jest.Mock;
  replace: jest.Mock;
  back: jest.Mock;
  forward: jest.Mock;
  refresh: jest.Mock;
  prefetch: jest.Mock;
  pathname: string;
  query: Record<string, string>;
  asPath: string;
}> = {}) {
  return {
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
    forward: jest.fn(),
    refresh: jest.fn(),
    prefetch: jest.fn(),
    pathname: '/',
    query: {},
    asPath: '/',
    ...overrides,
  };
}

/**
 * Create a wrapper component with optional providers
 */
function createWrapper(options: CustomRenderOptions = {}) {
  const { withWorkflow, initialDatasetId, wrapper: CustomWrapper } = options;

  // If no special providers are needed, just use the custom wrapper or no wrapper
  if (!withWorkflow && !CustomWrapper) {
    return undefined;
  }

  return function Wrapper({ children }: { children: React.ReactNode }) {
    let element = <>{children}</>;

    // Wrap with WorkflowProvider if requested
    if (withWorkflow) {
      // Note: This requires WorkflowProvider to be mocked or imported
      // For now, we'll create a placeholder. In actual tests, you'd import the real provider
      const MockWorkflowProvider = ({ children }: { children: React.ReactNode }) => (
        <div data-testid="workflow-provider">{children}</div>
      );
      element = <MockWorkflowProvider>{element}</MockWorkflowProvider>;
    }

    // Wrap with custom wrapper if provided
    if (CustomWrapper) {
      element = <CustomWrapper>{element}</CustomWrapper>;
    }

    return element;
  };
}

/**
 * Custom render function that wraps components with common providers
 *
 * @example
 * // Basic usage (no providers)
 * const { getByText } = renderWithProviders(<MyComponent />);
 *
 * @example
 * // With WorkflowProvider
 * const { getByText } = renderWithProviders(<MyComponent />, {
 *   withWorkflow: true,
 *   initialDatasetId: 'test-id'
 * });
 *
 * @example
 * // With custom wrapper
 * const { getByText } = renderWithProviders(<MyComponent />, {
 *   wrapper: ({ children }) => <CustomContext.Provider value={mockValue}>{children}</CustomContext.Provider>
 * });
 */
export function renderWithProviders(
  ui: ReactElement,
  options: CustomRenderOptions = {}
): RenderResult {
  const { initialRoute, ...renderOptions } = options;

  // Mock Next.js router if initial route is provided
  if (initialRoute) {
    // This would be mocked in jest.setup.js
    // For now, we're just acknowledging the option
  }

  const wrapper = createWrapper(options);

  return render(ui, {
    wrapper,
    ...renderOptions,
  });
}

/**
 * Helper to create a test wrapper with specific providers
 * Useful for reusing the same provider setup across multiple tests
 *
 * @example
 * const renderWithWorkflow = createTestWrapper({ withWorkflow: true });
 *
 * it('test 1', () => {
 *   renderWithWorkflow(<Component1 />);
 * });
 *
 * it('test 2', () => {
 *   renderWithWorkflow(<Component2 />);
 * });
 */
export function createTestWrapper(defaultOptions: CustomRenderOptions = {}) {
  return function renderWithDefaults(
    ui: ReactElement,
    options: CustomRenderOptions = {}
  ): RenderResult {
    return renderWithProviders(ui, {
      ...defaultOptions,
      ...options,
    });
  };
}

/**
 * Helper to get common test IDs used across components
 * Helps maintain consistency in test selectors
 */
export const TEST_IDS = {
  // Common UI elements
  dialog: 'dialog',
  modal: 'modal',
  spinner: 'loading-spinner',
  alert: 'alert',

  // Form elements
  form: 'form',
  submitButton: 'submit-button',
  cancelButton: 'cancel-button',

  // Recipe components
  recipeCard: 'recipe-card',
  recipeLibrary: 'recipe-library',
  recipeDialog: 'recipe-dialog',
  compatibilityBadge: 'compatibility-badge',

  // Transformation components
  transformationDialog: 'transformation-dialog',
  columnSelector: 'column-selector',
  transformationChain: 'transformation-chain',
} as const;

/**
 * Re-export testing library utilities for convenience
 */
export { screen, within, fireEvent, waitFor } from '@testing-library/react';
export * from './async-helpers';
