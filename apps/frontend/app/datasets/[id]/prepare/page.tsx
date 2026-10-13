import { redirect } from 'next/navigation';

/**
 * The dataset-scoped copy of the Data Preparation stage is gone (#999). This address
 * is kept only because the legacy `/datasets/[id]/engineer` page links here; it goes
 * when that page does (#738).
 */
export default async function LegacyPrepareRedirect(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  redirect(`/prepare?datasetId=${encodeURIComponent(id)}`);
}
