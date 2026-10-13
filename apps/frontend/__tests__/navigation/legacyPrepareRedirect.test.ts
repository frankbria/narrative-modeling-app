/**
 * #999: the dataset-scoped Prepare page is a redirect to the workflow stage.
 */
import { redirect } from 'next/navigation';
import LegacyPrepareRedirect from '@/app/datasets/[id]/prepare/page';

jest.mock('next/navigation', () => ({ redirect: jest.fn() }));

describe('/datasets/[id]/prepare', () => {
  it('sends the visitor to the Data Preparation stage for that dataset', async () => {
    await LegacyPrepareRedirect({ params: Promise.resolve({ id: 'abc 123' }) });

    expect(redirect).toHaveBeenCalledWith('/prepare?datasetId=abc%20123');
  });
});
