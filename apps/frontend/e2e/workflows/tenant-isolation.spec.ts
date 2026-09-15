import { test, expect } from '../fixtures';
import { API_BASE, apiAuthHeaders, signInAs } from '../helpers/apiAuth';
import { seedEvaluationWorkflow } from '../helpers/seedWorkflow';

/**
 * Tenant isolation, observed end to end through real auth (#493).
 *
 * Until #493 the e2e backend ran with SKIP_AUTH=true, which mapped EVERY request
 * to one user — so the only gate on main was structurally single-tenant and could
 * not see a cross-tenant read. This spec is the durable guard: tenant A (the
 * stored session) owns a dataset in both id-spaces, its base version, a workflow
 * and a trained model; tenant B (the second dev-credentials identity, #613) must
 * not be able to read any of them.
 *
 * A reads each surface first so a refusal below is isolation, not a dead token:
 * with a broken JWT both tenants would 401 and the "cannot read" checks would
 * pass vacuously.
 */
test.describe('tenant isolation (#493)', () => {
  test('a second signed-in user cannot read the first user\'s dataset, version, workflow or model @smoke', async ({
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

    const adminEmail = process.env.TEST_ADMIN_EMAIL;
    const adminSecret = process.env.TEST_ADMIN_PASSWORD;
    expect(adminEmail, 'TEST_ADMIN_EMAIL must be exported (test-e2e.sh does)').toBeTruthy();
    expect(adminSecret, 'TEST_ADMIN_PASSWORD must be exported (test-e2e.sh does)').toBeTruthy();

    const a = await apiAuthHeaders(request);
    const filename = `isolation-e2e-${Date.now()}.csv`;

    // --- Tenant A owns: a DatasetMetadata (+ its base DatasetVersion) ...
    const seeded = await request.post(`${API_BASE}/datasets/upload`, {
      headers: a,
      multipart: {
        file: { name: filename, mimeType: 'text/csv', buffer: Buffer.from('a,b\n1,2\n3,4\n') },
      },
    });
    expect(seeded.ok(), `seed upload failed: ${seeded.status()}`).toBeTruthy();
    const datasetId = (await seeded.json()).dataset_id as string;
    expect(datasetId).toBeTruthy();

    const versions = await request.get(`${API_BASE}/datasets/${datasetId}/versions`, { headers: a });
    expect(versions.status(), 'A lists its own versions').toBe(200);
    const versionId = (await versions.json()).versions?.[0]?.version_id as string | undefined;
    expect(versionId, 'the upload creates a base version').toBeTruthy();

    // ... a UserData-space dataset (the /upload page), its workflow, and a model.
    const fileId = await uploadTestDataset('ai-test-datasets/binary-classification-small.csv');
    const modelId = await trainModel(fileId, 'churned');
    await seedEvaluationWorkflow(page, request, fileId, modelId);

    const owned: Array<[string, string]> = [
      ['dataset', `/datasets/${datasetId}`],
      ['version list', `/datasets/${datasetId}/versions`],
      ['version', `/versions/${versionId}`],
      ['user_data', `/user_data/${fileId}`],
      ['workflow', `/workflows/${fileId}`],
      ['model', `/ml/${modelId}`],
    ];

    try {
      // --- A can read every surface (a dead token would fail here, not below).
      for (const [name, path] of owned) {
        const mine = await request.get(`${API_BASE}${path}`, { headers: a });
        expect(mine.status(), `A reads its own ${name}`).toBe(200);
      }

      // --- Tenant B: a genuinely different signed-in user.
      const bContext = await signInAs(browser, baseURL as string, adminEmail as string, adminSecret as string);
      try {
        const b = await apiAuthHeaders(bContext.request);
        expect(b.Authorization, 'B must hold a different token from A').not.toBe(a.Authorization);

        for (const [name, path] of owned) {
          const theirs = await bContext.request.get(`${API_BASE}${path}`, { headers: b });
          // 404 is the convention (unknown and foreign answer identically);
          // GET /datasets/{id} still answers 403 — either way, not readable.
          expect([403, 404], `B must not read A's ${name} (${path})`).toContain(theirs.status());
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
      } finally {
        await bContext.close();
      }
    } finally {
      await request.delete(`${API_BASE}/ml/${modelId}`, { headers: a }).catch(() => {});
      await request.delete(`${API_BASE}/datasets/${datasetId}`, { headers: a }).catch(() => {});
      await cleanupDataset(fileId);
    }
  });
});
