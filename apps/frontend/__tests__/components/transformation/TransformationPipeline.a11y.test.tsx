import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TransformationPipeline from '@/components/transformation/TransformationPipeline';

/**
 * Keyboard-accessibility regression tests for the data-preparation pipeline
 * (issue #275, WCAG 2.1.1). The pipeline must be fully operable without a
 * mouse: add steps, reorder them, and switch between the accessible Chain view
 * and the visual React Flow canvas — all from the keyboard.
 */
describe('TransformationPipeline — keyboard accessibility (#275)', () => {
  beforeEach(() => {
    // Component fires loadPreview + metadata fetches on mount. jest.setup makes
    // the default fetch REJECT, so stub it to a benign OK response here.
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
  });

  it('defaults to the accessible Chain view', () => {
    render(<TransformationPipeline datasetId="dataset-1" />);

    const chainToggle = screen.getByRole('button', { name: /^chain$/i });
    const visualToggle = screen.getByRole('button', { name: /^visual$/i });

    expect(chainToggle).toHaveAttribute('aria-pressed', 'true');
    expect(visualToggle).toHaveAttribute('aria-pressed', 'false');
    // The empty accessible list, not the drag-only canvas, is shown by default.
    expect(screen.getByText(/no transformations added yet/i)).toBeInTheDocument();
  });

  it('adds a transformation step using only the keyboard', async () => {
    const user = userEvent.setup();
    render(<TransformationPipeline datasetId="dataset-1" />);

    const addButton = screen.getByRole('button', { name: /add remove duplicates/i });
    addButton.focus();
    expect(addButton).toHaveFocus();

    await user.keyboard('{Enter}');

    const steps = screen.getAllByRole('listitem');
    expect(steps).toHaveLength(1);
    expect(within(steps[0]).getByText('Remove Duplicates')).toBeInTheDocument();
    expect(screen.queryByText(/no transformations added yet/i)).not.toBeInTheDocument();
  });

  it('reorders steps with keyboard shortcuts (Alt+ArrowDown)', async () => {
    const user = userEvent.setup();
    render(<TransformationPipeline datasetId="dataset-1" />);

    await user.click(screen.getByRole('button', { name: /add remove duplicates/i }));
    await user.click(screen.getByRole('button', { name: /add trim whitespace/i }));

    let steps = screen.getAllByRole('listitem');
    expect(within(steps[0]).getByText('Remove Duplicates')).toBeInTheDocument();

    // Move the first step down using the keyboard shortcut the list advertises.
    steps[0].focus();
    await user.keyboard('{Alt>}{ArrowDown}{/Alt}');

    steps = screen.getAllByRole('listitem');
    expect(within(steps[0]).getByText('Trim Whitespace')).toBeInTheDocument();
    expect(within(steps[1]).getByText('Remove Duplicates')).toBeInTheDocument();
  });

  it('keeps both views reachable via the keyboard-operable toggle', async () => {
    const user = userEvent.setup();
    render(<TransformationPipeline datasetId="dataset-1" />);

    const visualToggle = screen.getByRole('button', { name: /^visual$/i });
    visualToggle.focus();
    await user.keyboard('{Enter}');

    expect(visualToggle).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /^chain$/i })).toHaveAttribute(
      'aria-pressed',
      'false'
    );

    // ...and back to the Chain view.
    const chainToggle = screen.getByRole('button', { name: /^chain$/i });
    chainToggle.focus();
    await user.keyboard('{Enter}');
    expect(chainToggle).toHaveAttribute('aria-pressed', 'true');
  });
});
