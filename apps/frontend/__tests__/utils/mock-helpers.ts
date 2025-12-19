/**
 * Mock Helpers
 *
 * Utilities for creating mock API responses and test data
 */

/**
 * Recipe-related mock data types
 */
export interface MockRecipe {
  id: string;
  name: string;
  description: string;
  category: string;
  compatibility_score?: number;
  is_compatible?: boolean;
  transformations?: any[];
  created_at?: string;
  updated_at?: string;
  user_id?: string;
}

/**
 * Transformation-related mock data types
 */
export interface MockTransformation {
  id: string;
  name: string;
  type: string;
  config?: Record<string, any>;
  order?: number;
}

/**
 * Dataset-related mock data types
 */
export interface MockDataset {
  id: string;
  name: string;
  filename: string;
  status: string;
  row_count?: number;
  column_count?: number;
  columns?: Array<{ name: string; type: string }>;
  created_at?: string;
  updated_at?: string;
}

/**
 * Create a mock fetch response
 */
export function createMockResponse<T = any>(
  data: T,
  options: {
    status?: number;
    statusText?: string;
    ok?: boolean;
    headers?: Record<string, string>;
  } = {}
): Response {
  const {
    status = 200,
    statusText = 'OK',
    ok = status >= 200 && status < 300,
    headers = { 'Content-Type': 'application/json' },
  } = options;

  return {
    ok,
    status,
    statusText,
    headers: new Headers(headers),
    json: jest.fn().mockResolvedValue(data),
    text: jest.fn().mockResolvedValue(JSON.stringify(data)),
    blob: jest.fn().mockResolvedValue(new Blob([JSON.stringify(data)])),
    arrayBuffer: jest.fn().mockResolvedValue(new ArrayBuffer(0)),
    clone: jest.fn(),
    body: null,
    bodyUsed: false,
    redirected: false,
    type: 'basic',
    url: '',
    formData: jest.fn(),
  } as any as Response;
}

/**
 * Create a mock error response
 */
export function createMockErrorResponse(
  message: string,
  status: number = 400
): Response {
  return createMockResponse(
    { error: message },
    {
      status,
      statusText: message,
      ok: false,
    }
  );
}

/**
 * Mock recipe data builder
 */
export function createMockRecipe(overrides: Partial<MockRecipe> = {}): MockRecipe {
  return {
    id: 'recipe-1',
    name: 'Test Recipe',
    description: 'A test recipe for unit tests',
    category: 'data_cleaning',
    compatibility_score: 0.95,
    is_compatible: true,
    transformations: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    user_id: 'user-1',
    ...overrides,
  };
}

/**
 * Mock transformation data builder
 */
export function createMockTransformation(
  overrides: Partial<MockTransformation> = {}
): MockTransformation {
  return {
    id: 'transformation-1',
    name: 'Test Transformation',
    type: 'remove_duplicates',
    config: {},
    order: 0,
    ...overrides,
  };
}

/**
 * Mock dataset data builder
 */
export function createMockDataset(overrides: Partial<MockDataset> = {}): MockDataset {
  return {
    id: 'dataset-1',
    name: 'Test Dataset',
    filename: 'test.csv',
    status: 'ready',
    row_count: 100,
    column_count: 5,
    columns: [
      { name: 'id', type: 'string' },
      { name: 'name', type: 'string' },
      { name: 'age', type: 'number' },
      { name: 'email', type: 'string' },
      { name: 'active', type: 'boolean' },
    ],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

/**
 * Mock fetch for specific API endpoints
 * Returns a function that can be used to mock global.fetch
 */
export function createAPIFetchMock(
  responseMap: Record<string, any> = {}
): jest.Mock {
  return jest.fn((url: string, options?: RequestInit) => {
    const method = options?.method || 'GET';
    const key = `${method} ${url}`;

    // Check if we have a specific mock for this endpoint
    if (responseMap[key]) {
      return Promise.resolve(createMockResponse(responseMap[key]));
    }

    // Default responses based on URL patterns
    if (url.includes('/api/recipes')) {
      if (method === 'GET') {
        return Promise.resolve(
          createMockResponse({
            recipes: [createMockRecipe()],
            total: 1,
          })
        );
      }
      if (method === 'POST') {
        return Promise.resolve(createMockResponse(createMockRecipe()));
      }
    }

    if (url.includes('/api/transformations')) {
      if (method === 'GET') {
        return Promise.resolve(
          createMockResponse({
            transformations: [createMockTransformation()],
          })
        );
      }
    }

    if (url.includes('/api/datasets')) {
      if (method === 'GET') {
        return Promise.resolve(
          createMockResponse({
            datasets: [createMockDataset()],
            total: 1,
          })
        );
      }
    }

    // Default fallback - return empty success response
    return Promise.resolve(
      createMockResponse({
        success: true,
        message: 'Mock response',
      })
    );
  });
}

/**
 * Setup comprehensive API mocks for a test suite
 * Call this in beforeEach() to set up common API mocks
 */
export function setupAPIMocks(customMocks: Record<string, any> = {}) {
  const fetchMock = createAPIFetchMock(customMocks);
  global.fetch = fetchMock as any;
  return fetchMock;
}

/**
 * Mock successful recipe share operation
 */
export function mockRecipeShare(recipeId: string = 'recipe-1') {
  return createMockResponse({
    success: true,
    message: 'Recipe shared successfully',
    share_id: 'share-123',
    recipe_id: recipeId,
  });
}

/**
 * Mock successful recipe export operation
 */
export function mockRecipeExport(recipeId: string = 'recipe-1') {
  return createMockResponse({
    success: true,
    export_url: 'https://example.com/export/recipe-1.json',
    recipe_id: recipeId,
  });
}

/**
 * Mock compatibility check result
 */
export function mockCompatibilityCheck(
  isCompatible: boolean = true,
  score: number = 0.95
) {
  return createMockResponse({
    is_compatible: isCompatible,
    compatibility_score: score,
    issues: isCompatible ? [] : ['Data type mismatch in column "age"'],
  });
}

/**
 * Create a mock for localStorage
 * Useful for tests that use localStorage
 */
export function createLocalStorageMock() {
  let store: Record<string, string> = {};

  return {
    getItem: jest.fn((key: string) => store[key] || null),
    setItem: jest.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: jest.fn((key: string) => {
      delete store[key];
    }),
    clear: jest.fn(() => {
      store = {};
    }),
    get length() {
      return Object.keys(store).length;
    },
    key: jest.fn((index: number) => {
      const keys = Object.keys(store);
      return keys[index] || null;
    }),
  };
}

/**
 * Setup localStorage mock
 * Call this in beforeEach() or at the top of a test file
 */
export function setupLocalStorageMock() {
  const localStorageMock = createLocalStorageMock();
  Object.defineProperty(window, 'localStorage', {
    value: localStorageMock,
    writable: true,
  });
  return localStorageMock;
}

/**
 * Wait for async operations and state updates
 * Useful after triggering async actions
 */
export async function flushPromises() {
  return new Promise((resolve) => {
    setTimeout(resolve, 0);
  });
}

/**
 * Create a delay for testing loading states
 */
export function delay(ms: number = 100): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
