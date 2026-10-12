import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { mockPipelineFetch } from '@/__tests__/utils/pipelineFetch';
import TransformationPipeline from '@/components/transformation/TransformationPipeline';

/**
 * #862: the Visual canvas lets the user draw arrows between steps, and Preview and Apply
 * ignored them, sending the steps in the order they were added.
 *
 * jsdom has no layout, so an arrow cannot be dragged here. The canvas is replaced by one
 * button per possible arrow, each calling the component's own `onConnect`; everything
 * else in the library, and all of the component's state, is real.
 */
jest.mock('@xyflow/react', () => {
  const actual = jest.requireActual('@xyflow/react');
  type CanvasNode = { id: string; data: { label: string } };
  type CanvasProps = { nodes: CanvasNode[]; onConnect(arrow: { source: string; target: string }): void };
  const ReactFlow = (props: CanvasProps) => (
    <div data-testid="canvas">
      {props.nodes.flatMap((from) =>
        props.nodes.map((to) => (
          <button key={`${from.id}>${to.id}`} onClick={() => props.onConnect({ source: from.id, target: to.id })}>
            {`draw ${from.data.label} to ${to.data.label}`}
          </button>
        )),
      )}
    </div>
  );
  return { ...actual, ReactFlow };
});

const fetchMock = () => global.fetch as jest.Mock;

function respond(path: string, body: unknown) {
  const mountTime = fetchMock().getMockImplementation()!;
  fetchMock().mockImplementation(async (url: string, init?: RequestInit) =>
    String(url).endsWith(path) ? { ok: true, json: async () => body } : mountTime(url, init),
  );
}

const PREVIEW = { success: true, preview_data: [], stats_before: {}, stats_after: {} };

/** Add Trim Whitespace, Fill Missing and Remove Duplicates, in that order, then draw `arrows`. */
async function pipelineWith(...arrows: [string, string][]) {
  const user = userEvent.setup();
  render(<TransformationPipeline datasetId="dataset-1" />);
  for (const label of [/add trim whitespace/i, /add fill missing/i, /add remove duplicates/i]) {
    await user.click(await screen.findByRole('button', { name: label }));
  }
  await user.click(screen.getByRole('button', { name: 'Visual' }));
  for (const [from, to] of arrows) await user.click(screen.getByRole('button', { name: `draw ${from} to ${to}` }));
  return user;
}

function sent(path: string): string[][] {
  return fetchMock()
    .mock.calls.filter(([url]) => String(url).endsWith(path))
    .map(([, init]) => JSON.parse(init.body))
    .map((body) => (body.transformation_steps ?? [body]).map((s: { transformation_type: string }) => s.transformation_type));
}

beforeEach(() => mockPipelineFetch());

describe('TransformationPipeline: the order steps run in (#862)', () => {
  it('previews in the drawn order, not the order the steps were added in', async () => {
    respond('/transformations/preview', PREVIEW);
    const user = await pipelineWith(['Remove Duplicates', 'Trim Whitespace'], ['Trim Whitespace', 'Fill Missing']);

    await user.click(screen.getByRole('button', { name: /^preview$/i }));

    await waitFor(() =>
      expect(sent('/transformations/preview')).toEqual([['remove_duplicates', 'trim_whitespace', 'fill_missing']]),
    );
  });

  it('applies in the drawn order, one request per step', async () => {
    respond('/transformations/apply', { success: true });
    const user = await pipelineWith(['Remove Duplicates', 'Trim Whitespace'], ['Trim Whitespace', 'Fill Missing']);

    await user.click(screen.getByRole('button', { name: /apply & continue/i }));

    await waitFor(() =>
      expect(sent('/transformations/apply')).toEqual([['remove_duplicates'], ['trim_whitespace'], ['fill_missing']]),
    );
  });

  it('keeps the listed order when nothing is drawn', async () => {
    respond('/transformations/preview', PREVIEW);
    const user = await pipelineWith();

    await user.click(screen.getByRole('button', { name: /^preview$/i }));

    await waitFor(() =>
      expect(sent('/transformations/preview')).toEqual([['trim_whitespace', 'fill_missing', 'remove_duplicates']]),
    );
  });

  it.each([
    ['a step left unconnected', [['Trim Whitespace', 'Fill Missing']], /Remove Duplicates is not connected/],
    ['a fork', [['Trim Whitespace', 'Fill Missing'], ['Trim Whitespace', 'Remove Duplicates']], /Trim Whitespace leads to more than one step/],
    ['a loop', [['Trim Whitespace', 'Fill Missing'], ['Fill Missing', 'Remove Duplicates'], ['Remove Duplicates', 'Trim Whitespace']], /loop/],
  ] as [string, [string, string][], RegExp][])('refuses to preview or apply %s, and says why', async (_name, arrows, said) => {
    const user = await pipelineWith(...arrows);

    await user.click(screen.getByRole('button', { name: /^preview$/i }));
    expect(await screen.findByTestId('pipeline-error')).toHaveTextContent(said);
    await user.click(screen.getByRole('button', { name: /apply & continue/i }));
    expect(await screen.findByTestId('pipeline-error')).toHaveTextContent(/not one chain/);

    expect(sent('/transformations/preview')).toEqual([]);
    expect(sent('/transformations/apply')).toEqual([]);
  });

  it('a step added to a drawn chain joins its end', async () => {
    respond('/transformations/preview', PREVIEW);
    const user = await pipelineWith(['Remove Duplicates', 'Trim Whitespace'], ['Trim Whitespace', 'Fill Missing']);

    await user.click(screen.getByRole('button', { name: /add drop missing/i }));
    await user.click(screen.getByRole('button', { name: /^preview$/i }));

    await waitFor(() =>
      expect(sent('/transformations/preview')).toEqual([
        ['remove_duplicates', 'trim_whitespace', 'fill_missing', 'drop_missing'],
      ]),
    );
    expect(screen.queryByTestId('pipeline-error')).not.toBeInTheDocument();
  });

  it('lists the steps in the Chain view in the order they will run', async () => {
    const user = await pipelineWith(['Remove Duplicates', 'Trim Whitespace'], ['Trim Whitespace', 'Fill Missing']);

    await user.click(screen.getByRole('button', { name: 'Chain' }));

    const steps = within(screen.getByRole('list', { name: 'Transformation pipeline steps' })).getAllByRole('listitem');
    expect(steps.map((s) => s.getAttribute('aria-label'))).toEqual([
      'Step 1 of 3: Remove Duplicates',
      'Step 2 of 3: Trim Whitespace',
      'Step 3 of 3: Fill Missing',
    ]);
  });

  it('a reorder in the Chain view redraws the arrows, so both views agree', async () => {
    respond('/transformations/preview', PREVIEW);
    const user = await pipelineWith(['Remove Duplicates', 'Trim Whitespace'], ['Trim Whitespace', 'Fill Missing']);
    await user.click(screen.getByRole('button', { name: 'Chain' }));

    await user.click(screen.getByRole('button', { name: 'Move step 1 down' }));
    await user.click(screen.getByRole('button', { name: /^preview$/i }));

    await waitFor(() =>
      expect(sent('/transformations/preview')).toEqual([['trim_whitespace', 'remove_duplicates', 'fill_missing']]),
    );
    expect(screen.queryByTestId('pipeline-error')).not.toBeInTheDocument();
  });

  it('deleting the middle step in the Chain view leaves the rest connected', async () => {
    respond('/transformations/preview', PREVIEW);
    const user = await pipelineWith(['Remove Duplicates', 'Trim Whitespace'], ['Trim Whitespace', 'Fill Missing']);
    await user.click(screen.getByRole('button', { name: 'Chain' }));

    await user.click(screen.getByRole('button', { name: 'Delete step 2' }));
    await user.click(screen.getByRole('button', { name: /^preview$/i }));

    await waitFor(() => expect(sent('/transformations/preview')).toEqual([['remove_duplicates', 'fill_missing']]));
    expect(screen.queryByTestId('pipeline-error')).not.toBeInTheDocument();
  });

  it('an edit made in the Chain view lands on the step that was opened', async () => {
    respond('/transformations/preview', PREVIEW);
    const user = await pipelineWith(['Remove Duplicates', 'Trim Whitespace'], ['Trim Whitespace', 'Fill Missing']);
    await user.click(screen.getByRole('button', { name: 'Chain' }));

    // Step 3 in run order is Fill Missing, which was the second step added.
    await user.click(screen.getByRole('button', { name: 'Edit step 3' }));
    await user.type(within(await screen.findByRole('dialog')).getByLabelText(/^value/i), '0');
    await user.click(screen.getByRole('button', { name: 'Add transformation to pipeline' }));
    await user.click(screen.getByRole('button', { name: /^preview$/i }));

    await waitFor(() => {
      const preview = fetchMock().mock.calls.find(([url]) => String(url).endsWith('/transformations/preview'));
      expect(JSON.parse(preview![1].body).transformation_steps).toEqual([
        { transformation_type: 'remove_duplicates', parameters: {} },
        { transformation_type: 'trim_whitespace', parameters: {} },
        { transformation_type: 'fill_missing', parameters: { value: '0' } },
      ]);
    });
  });

  it('after an apply stops part-way, drops the steps that ran, which are the first in the drawn order', async () => {
    let applies = 0;
    const mountTime = fetchMock().getMockImplementation()!;
    fetchMock().mockImplementation(async (url: string, init?: RequestInit) => {
      if (!String(url).endsWith('/transformations/apply')) return mountTime(url, init);
      applies += 1;
      return { ok: true, json: async () => (applies === 1 ? { success: true } : { success: false, error: 'not numeric' }) };
    });
    const user = await pipelineWith(['Remove Duplicates', 'Trim Whitespace'], ['Trim Whitespace', 'Fill Missing']);

    await user.click(screen.getByRole('button', { name: /apply & continue/i }));
    expect(await screen.findByTestId('pipeline-error')).toHaveTextContent('Applied 1 of 3 steps. Step 2 (trim_whitespace) failed');
    await user.click(screen.getByRole('button', { name: 'Chain' }));

    const steps = within(screen.getByRole('list', { name: 'Transformation pipeline steps' })).getAllByRole('listitem');
    expect(steps.map((s) => s.getAttribute('aria-label'))).toEqual([
      'Step 1 of 2: Trim Whitespace',
      'Step 2 of 2: Fill Missing',
    ]);
  });
});
