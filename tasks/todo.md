# #770 — Truthful, activating onboarding (P1.52)

Scope: AC1, AC2, AC3, AC5, AC6, and AC4's deletion of verify-request.
Waiting on P0.36 (#765, needs-owner): AC4's value line on /auth/new-user and AC7 (one product name).
The CTA order is already Google, then GitHub.

## Steps
1. [ ] `apps/backend/scripts/generate_sample_datasets.py`: seeded numpy generator, no new deps. Writes
   churn (2 000 rows), house_prices (3 000) and marketing_response (2 500) with plausible signal.
2. [ ] `onboarding_service.get_sample_datasets`: the catalogue keeps only curated copy.
   `rows`, `columns`, `size_mb`, `preview_data` and `feature_columns` are read from the file (cached per process).
   `expected_accuracy` is re-measured with a quick-mode run.
   Drop `download_url` (no such route), `documentation_url` (dead domain) and `video_url`. Point help articles at
   `/quickstart` and drop the video tutorials (no videos exist). Update the schema to match.
3. [ ] Backend tests:
   - the catalogue matches the file; rows fall in 1 000–5 000
   - every sample trains in quick mode under FREE ceilings, with a score of at least the stated `expected_accuracy`
   - dead-link guard: every URL in the onboarding service output is app-relative and resolves to a frontend page
     or a mounted backend route
4. [ ] Frontend:
   - SampleDatasetSelector: drop the docs link and `download_url`; label the score R² for regression
   - dashboard empty state: explanation plus "Upload" and "Try a sample" buttons
   - delete `/auth/verify-request` and its `auth.ts` pages entry
   - auth/error: the request-access fallback uses `COMPANY.supportEmail`
   - grep guard banning `narrativeml.com` outside test fixtures
5. [ ] E2E `@smoke`: load a sample from the onboarding UI, train it on the real backend (quick), complete
   step 4, and assert that no onboarding request failed.

## Decisions (autonomous)
- Remove dead URLs rather than repoint them per sample. `/quickstart` is generic, so a per-sample
  "documentation" link to it would be fiction too.
- Regression's `expected_accuracy` is R² (what the engine reports), and the UI labels it that way.
