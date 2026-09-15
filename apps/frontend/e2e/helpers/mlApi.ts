/**
 * Shared backend base URL + auth for e2e specs that call the `/api/v1/ml` API
 * directly (Next.js does not proxy `/api/v1`). The backend verifies the
 * session's minted JWT (#493), so the header is read from the signed-in
 * request context — the same user the page loads as.
 */
export { API_BASE, apiAuthHeaders as mlAuth } from './apiAuth';
