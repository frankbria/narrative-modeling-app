import { useAsyncData } from '@/lib/hooks/useAsyncData';
import { loadColumns } from '@/lib/services/datasetColumns';
import { modelService, type TrainingMode } from '@/lib/services/model';

/** What the setup form offers: the dataset's columns and the recommended mode. */

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
