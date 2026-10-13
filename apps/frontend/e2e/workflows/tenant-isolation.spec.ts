import { test, expect } from '../fixtures';
import { API_BASE, apiAuthHeaders } from '../helpers/apiAuth';
import { isolatedState } from '../isolatedUsers';
import { seedEvaluationWorkflow } from '../helpers/seedWorkflow';

/**
 * Tenant isolation, observed end to end through real auth (#493).
 *
 * Until #493 the e2e backend ran with SKIP_AUTH=true, which mapped EVERY request
 * to one user — so the only gate on main was structurally single-tenant and could
 * not see a cross-tenant read. This spec is the durable guard: tenant A (the
 * stored session) owns a dataset in both id-spaces, its base version, a workflow
 * a trained model, that upload's column statistics and a batch-prediction job
 * (#753); tenant B must not be able to read or change any of them, and B's own
 * data is unaffected by A's.
 *
 * B is the isolated `tenant-b` user (#743), not the admin: the admin tenant's plan
 * has an upload ceiling another spec depends on, and B uploads here.
 *
 * A reads each surface first so a refusal below is isolation, not a dead token:
 * with a broken JWT both tenants would 401 and the "cannot read" checks would
 * pass vacuously.
 */
// Three rows of the training file's inputs (binary-classification-small.csv, without its target).
const BATCH_ROWS = [
  'age,tenure,monthly_charges,contract_type,has_internet,has_phone,payment_method,total_charges,support_calls',
  '48,28,79.49,Two year,true,false,Bank Transfer,2323.18,5',
  '18,33,106.74,Two year,false,true,Credit Card,3758.47,2',
  '35,12,55.10,Two year,true,true,Bank Transfer,661.20,1',
].join('\n');

test.describe('tenant isolation (#493)', () => {
  test('a second signed-in user cannot read or change the first user\'s data, and keeps its own @smoke', async ({
    authenticatedPage: page,
    request,
    uploadTestDataset,
    trainModel,
    cleanupDataset,
    browser,
    baseURL,
  }) => {
    // Real AutoML training + the artifact poll can exceed the default timeout.
    test.setTimeout(180000);

    const a = await apiAuthHeaders(request);
    const filename = `isolation-e2e-${Date.now()}.csv`;

    // Created inside the try so a failure mid-setup (training can time out)
    // still reaches the cleanup in `finally` instead of orphaning A's objects.
    let datasetId: string | undefined;
    let fileId: string | undefined;
    let modelId: string | undefined;
    let jobId: string | undefined;
    try {
      // --- Tenant A owns: a DatasetMetadata (+ its base DatasetVersion) ...
      const seeded = await request.post(`${API_BASE}/datasets/upload`, {
        headers: a,
        multipart: {
          file: { name: filename, mimeType: 'text/csv', buffer: Buffer.from('a,b\n1,2\n3,4\n') },
        },
      });
      expect(seeded.ok(), `seed upload failed: ${seeded.status()}`).toBeTruthy();
      datasetId = (await seeded.json()).dataset_id as string;
      expect(datasetId).toBeTruthy();

      const versions = await request.get(`${API_BASE}/datasets/${datasetId}/versions`, { headers: a });
      expect(versions.status(), 'A lists its own versions').toBe(200);
      const versionId = (await versions.json()).versions?.[0]?.version_id as string | undefined;
      expect(versionId, 'the upload creates a base version').toBeTruthy();

      // ... a UserData-space dataset (the /upload page), its workflow, and a model.
      fileId = await uploadTestDataset('ai-test-datasets/binary-classification-small.csv');
      modelId = await trainModel(fileId, 'churned');
      await seedEvaluationWorkflow(page, request, fileId, modelId);

      // ... and a batch-prediction job on that model: three rows, no second training run.
      const created = await request.post(`${API_BASE}/batch/jobs`, {
        headers: a,
        multipart: {
          model_id: modelId,
          file: { name: 'isolation-batch.csv', mimeType: 'text/csv', buffer: Buffer.from(BATCH_ROWS) },
        },
      });
      expect(created.status(), `A creates a batch job: ${await created.text()}`).toBe(200);
      jobId = (await created.json()).job_id as string;

      const owned: Array<[string, string]> = [
        ['dataset', `/datasets/${datasetId}`],
        ['version list', `/datasets/${datasetId}/versions`],
        ['version', `/versions/${versionId}`],
        ['user_data', `/user_data/${fileId}`],
        ['workflow', `/workflows/${fileId}`],
        ['model', `/ml/${modelId}`],
        ['column statistics', `/column_stats/dataset/${fileId}`],
        ['batch job', `/batch/jobs/${jobId}`],
        ['batch job progress', `/batch/jobs/${jobId}/progress`],
      ];

      // --- A can read every surface (a dead token would fail here, not below).
      for (const [name, path] of owned) {
        const mine = await request.get(`${API_BASE}${path}`, { headers: a });
        expect(mine.status(), `A reads its own ${name}`).toBe(200);
      }

      // --- Tenant B: a genuinely different signed-in user.
      const bContext = await browser.newContext({ baseURL, storageState: isolatedState('tenant-b') });
      let bDatasetId: string | undefined;
      try {
        const b = await apiAuthHeaders(bContext.request);
        expect(b.Authorization, 'B must hold a different token from A').not.toBe(a.Authorization);

        for (const [name, path] of owned) {
          const theirs = await bContext.request.get(`${API_BASE}${path}`, { headers: b });
          // 404 on every surface: a foreign id answers like an unknown one, so
          // no response confirms that the id exists (#751).
          expect(theirs.status(), `B must not read A's ${name} (${path})`).toBe(404);
          expect(await theirs.text(), `B's ${name} response must not carry A's data`).not.toContain(filename);
        }

        // And A's dataset is absent from B's own listing.
        const listing = await bContext.request.get(`${API_BASE}/datasets?page=1&limit=100`, { headers: b });
        expect(listing.status()).toBe(200);
        expect(await listing.text()).not.toContain(filename);

        // Write paths too: B can neither delete A's model nor rewrite A's workflow,
        // and A's objects are untouched afterwards.
        const del = await bContext.request.delete(`${API_BASE}/ml/${modelId}`, { headers: b });
        expect([403, 404], "B must not delete A's model").toContain(del.status());
        const put = await bContext.request.put(`${API_BASE}/workflows/${fileId}`, {
          headers: { ...b, 'Content-Type': 'application/json' },
          data: { current_stage: 'data_loading', completed_stages: [], stage_data: {} },
        });
        expect([403, 404], "B must not rewrite A's workflow").toContain(put.status());
        expect((await request.get(`${API_BASE}/ml/${modelId}`, { headers: a })).status(), "A's model survives B's delete").toBe(200);
        const workflow = await request.get(`${API_BASE}/workflows/${fileId}`, { headers: a });
        expect(workflow.status()).toBe(200);
        expect((await workflow.json()).current_stage, "A's workflow survives B's put").toBe('model_evaluation');

        // The batch job's write paths, and its results (#753).
        for (const [what, call] of [
          ['cancel', () => bContext.request.post(`${API_BASE}/batch/jobs/${jobId}/cancel`, { headers: b })],
          ['delete', () => bContext.request.delete(`${API_BASE}/batch/jobs/${jobId}`, { headers: b })],
          ['download', () => bContext.request.get(`${API_BASE}/batch/jobs/${jobId}/download`, { headers: b })],
        ] as const) {
          expect((await call()).status(), `B must not ${what} A's batch job`).toBe(404);
        }
        const job = await request.get(`${API_BASE}/batch/jobs/${jobId}`, { headers: a });
        expect(job.status(), "A's batch job survives B's cancel and delete").toBe(200);
        expect((await job.json()).status, "B's cancel did not land").not.toBe('cancelled');

        // The other direction (#753): B's own data, while A's exists.
        const bFilename = `isolation-b-${Date.now()}.csv`;
        const bSeeded = await bContext.request.post(`${API_BASE}/datasets/upload`, {
          headers: b,
          multipart: {
            file: { name: bFilename, mimeType: 'text/csv', buffer: Buffer.from('c,d\n5,6\n7,8\n') },
          },
        });
        expect(bSeeded.ok(), `B uploads its own dataset: ${bSeeded.status()}`).toBeTruthy();
        bDatasetId = (await bSeeded.json()).dataset_id as string;

        const bList = await (await bContext.request.get(`${API_BASE}/datasets?page=1&limit=100`, { headers: b })).text();
        expect(bList, "B's list holds B's dataset").toContain(bFilename);
        expect(bList, "B's list does not hold A's").not.toContain(filename);
        const aList = await (await request.get(`${API_BASE}/datasets?page=1&limit=100`, { headers: a })).text();
        expect(aList, "A's list holds A's dataset").toContain(filename);
        expect(aList, "A's list does not hold B's").not.toContain(bFilename);
        expect(
          (await request.get(`${API_BASE}/datasets/${bDatasetId}`, { headers: a })).status(),
          "A must not read B's dataset either",
        ).toBe(404);
      } finally {
        if (bDatasetId) {
          const b = await apiAuthHeaders(bContext.request);
          await bContext.request.delete(`${API_BASE}/datasets/${bDatasetId}`, { headers: b }).catch(() => {});
        }
        await bContext.close();
      }
    } finally {
      if (jobId) await request.delete(`${API_BASE}/batch/jobs/${jobId}`, { headers: a }).catch(() => {});
      if (modelId) await request.delete(`${API_BASE}/ml/${modelId}`, { headers: a }).catch(() => {});
      if (datasetId) await request.delete(`${API_BASE}/datasets/${datasetId}`, { headers: a }).catch(() => {});
      if (fileId) await cleanupDataset(fileId);
    }
  });
});
