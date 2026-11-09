// The data fixtures' types; the implementations live in ./index.ts.
export type DataFixtures = {
  testCSV: Buffer;
  /** `uploadAs` names the uploaded file, so a test can find its own rows among earlier runs'. */
  uploadTestDataset: (fileName?: string, uploadAs?: string) => Promise<string>;
  cleanupDataset: (datasetId: string) => Promise<void>;
  trainModel: (
    datasetId: string,
    targetColumn: string,
    trainingConfig?: Record<string, unknown>,
  ) => Promise<string>;
  cleanupModel: (modelId: string) => Promise<void>;
};

