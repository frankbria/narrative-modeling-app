/**
 * A fetch stub for the Prepare pipeline's mount-time calls (#855): the real registry
 * (captured from the backend by test_transformation_request_schemas_fixture.py) for
 * GET /transformations/available, a few rows for GET /data/{id}/preview, and a benign
 * OK for anything else.
 */
import registry from '@/__tests__/fixtures/availableTransformations.json';

export const pipelineRows = {
  columns: ['name', 'score'],
  data: [{ name: ' alice ', score: 10 }, { name: 'bob', score: null }],
};

export function mockPipelineFetch() {
  (global.fetch as jest.Mock).mockImplementation(async (url: string) => {
    if (String(url).endsWith('/transformations/available')) return { ok: true, json: async () => registry };
    if (/\/data\/[^/]+\/preview$/.test(String(url))) return { ok: true, json: async () => pipelineRows };
    return { ok: true, json: async () => ({}) };
  });
}
