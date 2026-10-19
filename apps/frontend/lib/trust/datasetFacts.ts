/**
 * Figures the public /security page states about a dataset. Each is held to the backend
 * line it describes by apps/backend/tests/test_security/test_trust_page_facts.py.
 */
/** `dataset_s3_key` (utils/s3.py): the extension is the upload's own, lower-cased. */
export const DATASET_KEY_TEMPLATE = 'datasets/<account id>/<random id>.<extension>'
/** The same function with `masked=True`, as `_store_confirmed` writes a masked CSV. */
export const MASKED_KEY_TEMPLATE = 'datasets/<account id>/masked_<random id>.csv'
/** `PIIDetector.detect_pii_in_dataframe(sample_size=...)`. */
export const PII_SCAN_SAMPLE_ROWS = 100
/** The `PIIType`s the value patterns look for. */
export const PII_VALUE_CATEGORIES = ['email', 'phone', 'ssn', 'credit_card', 'ip_address'] as const
/** The `PIIType`s a column name is matched against: a larger set than the value patterns. */
export const PII_NAME_CATEGORIES = [
  'email',
  'phone',
  'ssn',
  'name',
  'address',
  'date_of_birth',
  'medical_id',
  'financial_account',
] as const
/** `infer_schema` keeps this many example values per column, and the upload summary sends them. */
export const SUMMARY_EXAMPLE_VALUES = 3
/** `DatasetSummarizationService` (the Explore AI Insights panel): `sample_data[:N]`. */
export const AI_SAMPLE_ROWS = 5
