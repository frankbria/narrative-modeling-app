import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { mockPipelineFetch } from '@/__tests__/utils/pipelineFetch';
import TransformationPipeline from '@/components/transformation/TransformationPipeline';

/**
 * What the user sees when they preview or apply (#855). Every action used to fail
 * against the API (422/404) and only log to the console, so the screen showed nothing.
 */
const fetchMock = () => global.fetch as jest.Mock;

/** Route the action calls; everything else gets the pipeline's mount-time stubs. */
function respond(path: string, body: unknown) {
  const mountTime = fetchMock().getMockImplementation()!;
  fetchMock().mockImplementation(async (url: string, init?: RequestInit) =>
    String(url).endsWith(path) ? { ok: true, json: async () => body } : mountTime(url, init),
  );
}

async function addTrimWhitespace() {
  const user = userEvent.setup();
  render(<TransformationPipeline datasetId="dataset-1" onComplete={onComplete} />);
  await user.click(await screen.findByRole('button', { name: /add trim whitespace/i }));
  return user;
}

const onComplete = jest.fn();

beforeEach(() => {
  mockPipelineFetch();
  onComplete.mockReset();
});

describe('TransformationPipeline actions (#855)', () => {
  it('shows the previewed rows in the After table', async () => {
    respond('/transformations/preview', {
      success: true,
      preview_data: [{ name: 'alice', score: 10 }],
      stats_before: { row_count: 2, column_count: 2 },
      stats_after: { row_count: 2, column_count: 2 },
    });
    const user = await addTrimWhitespace();

    await user.click(screen.getByRole('button', { name: /^preview$/i }));
    await user.click(await screen.findByRole('button', { name: /^after$/i }));

    expect(await screen.findByText('alice')).toBeInTheDocument();
  });

  it('shows a failed apply to the user, naming the step', async () => {
    respond('/transformations/apply', { success: false, error: 'Transformations support CSV and Parquet files' });
    const user = await addTrimWhitespace();

    await user.click(screen.getByRole('button', { name: /apply & continue/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Step 1 (trim_whitespace) failed: Transformations support CSV and Parquet files',
    );
    expect(onComplete).not.toHaveBeenCalled();
  });

  it('confirms a successful apply and hands back the same dataset', async () => {
    respond('/transformations/apply', { success: true });
    const user = await addTrimWhitespace();

    await user.click(screen.getByRole('button', { name: /apply & continue/i }));

    expect(await screen.findByText('Applied 1 transformation')).toBeInTheDocument();
    await waitFor(() => expect(onComplete).toHaveBeenCalledWith('dataset-1'));
  });
});
