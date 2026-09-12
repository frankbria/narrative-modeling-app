# Issue #467 — [P0.24] [data-integrity] Applying a transformation overwrites DatasetMetadata.s3_url and severs the link between the id-spaces

Plan source: self-authored. Fork: (a) update both twins in one write vs (b) stable id on both documents + migration.
Chosen (a): the join is `(user_id, s3_url)` in exactly one place (erasure); a helper that moves BOTH twins to the
new file keeps it intact today and also fixes #627; (b) is a schema+migration change the operator must run —
filed as the follow-up if the inventory (AC4) shows broken links worth repairing.

## Design
- `app/services/dataset_link.py::record_new_file(doc, new_url)`: given either twin, find the other via the OLD
  `(user_id, s3_url)`, point both `file_path` and `s3_url` at `new_url`, keep the original upload in
  `DatasetMetadata.source_s3_url` (new optional field) the first time, save both. Twin missing → update the one.
- Writers: transformation_service (apply), bulk_transformation_service, transformations.py (UserData routes),
  data_issues.py (2) → all through the helper. Readers untouched (they use `downloadable_url`, #466).
- AC2: LocalStack test — upload (dual-write), transform for real, then the training data loader reads the twin and
  gets the TRANSFORMED bytes (assert on the downloaded key / row shape).
- AC3: erasure after a transformation still removes the UserData twin (real docs).
- AC4: `scripts/inventory_dataset_links.py` counts twins with no partner on `(user_id, s3_url)` per side; operator runs
  it against production and posts the count on the issue.
- AC5: original object retained (`source_s3_url`), lifecycle → #529, cleanup → #525 (comments).

## Steps
1. [ ] RED: link helper tests; erasure-after-transform; LocalStack transform→train-loader
2. [ ] GREEN: field + helper + five writers
3. [ ] Inventory script + test
4. [ ] Docs: CLAUDE.md two-id-spaces bullet

## Acceptance criteria
- [ ] AC1 link survives (both twins moved in one helper)
- [ ] AC2 training reads the transformed file
- [ ] AC3 erasure reaches the twin after a transformation
- [ ] AC4 inventory script; operator posts the count
- [ ] AC5 original retained deliberately; lifecycle/cleanup pointers
