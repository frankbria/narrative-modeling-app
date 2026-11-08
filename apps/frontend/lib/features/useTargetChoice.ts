import { useState } from 'react';

interface Picked {
  datasetId: string | undefined;
  column: string;
}

/** The column to predict: the user's pick for this dataset, else the one the Features stage recorded. */
export function useTargetChoice(datasetId: string | undefined, recorded: string) {
  const [picked, setPicked] = useState<Picked | null>(null);
  const mine = picked !== null && picked.datasetId === datasetId;
  const target = mine ? picked.column : recorded;
  return { target, setTarget: (column: string) => setPicked({ datasetId, column }) };
}
