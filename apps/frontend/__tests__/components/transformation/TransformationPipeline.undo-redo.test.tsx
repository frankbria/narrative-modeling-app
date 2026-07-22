import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TransformationPipeline from '@/components/transformation/TransformationPipeline';

/**
 * Undo/Redo regression tests for the data-preparation pipeline (issue #281).
 * Before the fix the toolbar Undo/Redo buttons had no onClick and gated on a
 * `historyIndex` that was never updated — Undo was always disabled and Redo
 * never worked. History is now recorded from structural changes.
 */
describe('TransformationPipeline — Undo/Redo (#281)', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
  });

  it('Undo starts disabled and Undo/Redo reverse a structural change', async () => {
    const user = userEvent.setup();
    render(<TransformationPipeline datasetId="dataset-1" />);

    const undo = screen.getByTitle('Undo');
    const redo = screen.getByTitle('Redo');

    // Nothing to undo yet.
    expect(undo).toBeDisabled();
    expect(redo).toBeDisabled();
    expect(screen.getByText(/no transformations added yet/i)).toBeInTheDocument();

    // Add a step → it becomes undoable.
    await user.click(screen.getByRole('button', { name: /add remove duplicates/i }));
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
    expect(undo).toBeEnabled();
    expect(redo).toBeDisabled();

    // Undo removes the step.
    await user.click(undo);
    expect(screen.queryAllByRole('listitem')).toHaveLength(0);
    expect(screen.getByText(/no transformations added yet/i)).toBeInTheDocument();
    expect(undo).toBeDisabled();
    expect(redo).toBeEnabled();

    // Redo restores it.
    await user.click(redo);
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
    expect(undo).toBeEnabled();
    expect(redo).toBeDisabled();
  });

  it('does not record undo entries for unrelated re-renders (position-agnostic)', async () => {
    const user = userEvent.setup();
    render(<TransformationPipeline datasetId="dataset-1" />);

    const undo = screen.getByTitle('Undo');

    await user.click(screen.getByRole('button', { name: /add remove duplicates/i }));
    await user.click(screen.getByRole('button', { name: /add trim whitespace/i }));
    expect(screen.getAllByRole('listitem')).toHaveLength(2);

    // Two undos should peel back exactly the two structural additions.
    await user.click(undo);
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
    await user.click(undo);
    expect(screen.queryAllByRole('listitem')).toHaveLength(0);
    expect(undo).toBeDisabled();
  });
});
