/**
 * Shared test data for e2e specs that train on the trainable
 * `binary-classification-small.csv` dataset (#195). The 6-row `sample.csv`
 * makes AutoML detect problem type "unknown" and fail, so any test that trains
 * a real model must use this dataset + the `churned` target.
 *
 * The 9 feature columns (target `churned` excluded) mirror the dataset header;
 * if that header changes, update these payloads to match.
 */

/** Relative path passed to the `uploadTestDataset` fixture. */
export const BINARY_CLASS_DATASET = 'ai-test-datasets/binary-classification-small.csv';

/** Target column for `trainModel`. */
export const BINARY_CLASS_TARGET = 'churned';

export interface BinaryClassRow {
  age: number;
  tenure: number;
  monthly_charges: number;
  contract_type: string;
  has_internet: boolean;
  has_phone: boolean;
  payment_method: string;
  total_charges: number;
  support_calls: number;
}

/** One valid feature record the fitted pipeline can transform. */
export const BINARY_CLASS_ROW: BinaryClassRow = {
  age: 35,
  tenure: 12,
  monthly_charges: 65.5,
  contract_type: 'Month-to-month',
  has_internet: true,
  has_phone: true,
  payment_method: 'Electronic Check',
  total_charges: 800.0,
  support_calls: 2,
};

const CONTRACT_TYPES = ['Month-to-month', 'One year', 'Two year'];
const PAYMENT_METHODS = ['Electronic Check', 'Credit Card', 'Bank Transfer', 'Mailed Check'];

/**
 * Generate `n` varied-but-valid feature rows for batch-style prediction.
 * Values stay within the dataset's observed ranges so the feature engineer
 * accepts every categorical value.
 */
export function makeBinaryClassRows(n: number): BinaryClassRow[] {
  return Array.from({ length: n }, (_, i) => {
    const tenure = 1 + (i % 72); // 1–72
    const monthly = 20 + (i % 81); // 20–100
    return {
      age: 20 + (i % 41), // 20–60
      tenure,
      monthly_charges: monthly,
      contract_type: CONTRACT_TYPES[i % CONTRACT_TYPES.length],
      has_internet: i % 2 === 0,
      has_phone: i % 3 !== 0,
      payment_method: PAYMENT_METHODS[i % PAYMENT_METHODS.length],
      total_charges: Number((tenure * monthly).toFixed(2)),
      support_calls: i % 11, // 0–10
    };
  });
}
