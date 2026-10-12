import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';
import { modelService, type TrainingMode } from '@/lib/services/model';

/** What the setup form offers: the dataset's columns and the recommended mode. */

type DatasetRecord = {
  columns?: string[] | null;
  data_schema?: { field_name: string }[] | null;
};

function columnNames(record: DatasetRecord): string[] {
  if (record.columns?.length) return record.columns;
  return (record.data_schema ?? []).map((field) => field.field_name);
}

async function readColumns(path: string, token: string | null): Promise<string[]> {
  const response = await fetch(`${API_URL}/${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return response.ok ? columnNames(await response.json()) : [];
}

/**
 * The upload page hands this stage a UserData id, which only /user_data answers
 * for; a /datasets upload is the other id-space, and keeps its names in
 * `columns` with data_schema always empty (#919).
 */
async function loadColumns(datasetId: string): Promise<string[]> {
  const token = await getAuthToken();
  const fromUpload = await readColumns(`user_data/${datasetId}`, token);
  if (fromUpload.length) return fromUpload;
  return readColumns(`datasets/${datasetId}`, token);
}

function loadRecommendation(datasetId: string) {
  // Advisory only: a failure just leaves the Quick default in place.
  return modelService.getModeRecommendation(datasetId).catch((error) => {
    console.error('Failed to load mode recommendation:', error);
    return null;
  });
}

/**
 * A user pick beats the recommendation, including one that arrives later: null
 * means "untouched", so a late recommendation simply shows through (issue #101).
 */
export function chosenMode(
  picked: TrainingMode | null,
  recommended: TrainingMode | undefined,
): TrainingMode {
  return picked ?? recommended ?? 'quick';
}

export function useTrainingOptions(datasetId: string | null | undefined) {
  const enabled = Boolean(datasetId);
  // Two independent loads, deliberately NOT combined: the recommendation is
  // advisory and can be slow, and folding it in with the columns would make the
  // whole form wait on it. A test pins that.
  const { data: columns } = useAsyncData(() => loadColumns(datasetId as string), [datasetId], {
    enabled,
  });
  const { data: recommendation } = useAsyncData(
    () => loadRecommendation(datasetId as string),
    [datasetId],
    { enabled },
  );
  return {
    columns: columns ?? [],
    recommendedMode: recommendation?.recommended_mode,
    reason: recommendation?.reason,
  };
}
