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
   * Additional wrapper components to wrap around the component under test
   */
  wrapper?: React.ComponentType<{ children: React.ReactNode }>;
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
 * Creates a wrapper component for the provided custom wrapper, if any.
 *
 * This function returns the custom wrapper component if provided, or undefined
 * if no wrapper is needed (optimization to avoid unnecessary React elements).
 *
 * @param {CustomRenderOptions} options - Configuration for wrapper composition
 * @param {React.ComponentType} options.wrapper - Custom wrapper component to use
 *
 * @returns {React.ComponentType | undefined} The custom wrapper component, or undefined
 *   if no wrapper is provided
 *
 * @internal This is an internal helper function for renderWithProviders
 *
 * @example
 * // Returns undefined (no wrapping needed)
 * const wrapper = createWrapper({});
 *
 * @example
 * // Returns the custom provider
 * const wrapper = createWrapper({
 *   wrapper: ({ children }) => <CustomContext.Provider>{children}</CustomContext.Provider>
 * });
 */
function createWrapper(options: CustomRenderOptions = {}) {
  const { wrapper: CustomWrapper } = options;

  // If no wrapper is provided, return undefined to avoid unnecessary wrapping
  if (!CustomWrapper) {
    return undefined;
  }

  // Return the custom wrapper directly
  return CustomWrapper;
}

/**
 * Custom render function that wraps components with optional custom providers
 *
 * @example
 * // Basic usage (no providers)
 * const { getByText } = renderWithProviders(<MyComponent />);
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
 * const CustomProvider = ({ children }) => (
 *   <ThemeProvider theme={mockTheme}>{children}</ThemeProvider>
 * );
 *
 * const renderWithTheme = createTestWrapper({ wrapper: CustomProvider });
 *
 * it('test 1', () => {
 *   renderWithTheme(<Component1 />);
 * });
 *
 * it('test 2', () => {
 *   renderWithTheme(<Component2 />);
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
