import { useSession } from 'next-auth/react';
import { getAuthToken } from '@/lib/auth-helpers';
import { API_URL } from '@/lib/constants';
import { apiError } from '@/lib/services/apiError';
import { useAsyncData } from '@/lib/hooks/useAsyncData';

interface AISummary {
  rawMarkdown: string;
}

// Cache duration in milliseconds (5 minutes)
const CACHE_DURATION = 5 * 60 * 1000;

// In-memory cache for AI summaries
const summaryCache: Record<string, { data: AISummary; timestamp: number }> = {};

const OBJECT_ID = /^[0-9a-f]{24}$/i;

/** GET a user_data path; a 404 means "nothing there yet", not a failure. */
async function getOrNull(path: string): Promise<Record<string, unknown> | null> {
  const response = await fetch(`${API_URL}/user_data/${path}`, {
    headers: { Authorization: `Bearer ${await getAuthToken()}` },
  });
  if (response.status === 404) return null;
  if (!response.ok) throw await apiError(response, 'We could not load the analysis of your data.');
  return response.json();
}

/** Anything that is not a dataset id (the chat passes the user id) means "my latest dataset". */
async function resolveDatasetId(id: string): Promise<string | null> {
  if (OBJECT_ID.test(id)) return id;
  const latest = await getOrNull('latest');
  return typeof latest?._id === 'string' ? latest._id : null;
}

async function loadSummary(id: string): Promise<AISummary | null> {
  const cached = summaryCache[id];
  if (cached && Date.now() - cached.timestamp < CACHE_DURATION) return cached.data;

  const datasetId = await resolveDatasetId(id);
  const data = datasetId ? ((await getOrNull(`${datasetId}/ai-summary`)) as AISummary | null) : null;
  if (data) summaryCache[id] = { data, timestamp: Date.now() };
  return data;
}

/**
 * Hook to fetch and use the AI summary context for a dataset
 * @param datasetId The ID of the dataset, or of the user (meaning their latest dataset)
 * @returns Object containing the context string, raw markdown, and loading/error states
 */
export function useDatasetChatContext(datasetId: string | null) {
  // `session` is a NEW OBJECT every render, so keying on it re-fetched forever (#402).
  const userId = useSession().data?.user?.id;
  const summary = useAsyncData(() => loadSummary(datasetId as string), [datasetId, userId], {
    enabled: !!datasetId && !!userId,
  });
  const rawMarkdown = summary.data?.rawMarkdown ?? null;

  return {
    contextString: rawMarkdown,
    rawMarkdown,
    isLoading: summary.loading,
    error: summary.error,
    isAvailable: rawMarkdown !== null,
  };
}
