/**
 * Shared backend base URL + auth header for e2e specs that call the
 * `/api/v1/ml` API directly (Next.js does not proxy `/api/v1`, and the
 * SKIP_AUTH backend still requires an Authorization header for HTTPBearer).
 *
 * The token matches the `trainModel`/`uploadTestDataset` fixtures so all calls
 * resolve to the same SKIP_AUTH user.
 */
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
export const ML_AUTH = { Authorization: 'Bearer e2e-test-token' };
