import { API_URL } from '@/lib/constants';
import { getAuthToken } from '@/lib/auth-helpers';

type DatasetRecord = {
  columns?: string[] | null;
  data_schema?: { field_name: string }[] | null;
};

function columnNames(record: DatasetRecord): string[] {
  if (record.columns?.length) return record.columns;
  return (record.data_schema ?? []).map((field) => field.field_name);
}

async function readColumns(path: string, token: string | null): Promise<string[]> {
  const response = await fetch(`${API_URL}/${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return response.ok ? columnNames(await response.json()) : [];
}

/**
 * The names of a dataset's columns, for the stages that let the user pick among them.
 *
 * The upload page hands the workflow a UserData id, which only /user_data answers
 * for; a /datasets upload is the other id-space, and keeps its names in
 * `columns` with data_schema always empty (#919). Empty when neither answers.
 */
export async function loadColumns(datasetId: string): Promise<string[]> {
  const token = await getAuthToken();
  const fromUpload = await readColumns(`user_data/${datasetId}`, token);
  if (fromUpload.length) return fromUpload;
  return readColumns(`datasets/${datasetId}`, token);
}
