import React from 'react';
import { render, screen } from '@testing-library/react';
import PreviewPanel from '@/components/transformation/PreviewPanel';
import PipelineToolbar from '@/components/transformation/PipelineToolbar';
import { DataPreviewTable } from '@/components/DataPreviewTable';

// jsdom has no layout engine: these pin the classes that contain the overflow.
// The real-browser check is e2e/workflows/data-preparation.spec.ts: /prepare at 1440px and
// /explore/{id} at 390px must not scroll the page sideways.
const rows = Array.from({ length: 100 }, (_, i) => [i, 'x']);
const preview = { before: { columns: ['a', 'b'], data: rows }, after: { columns: ['a', 'b'], data: rows } };

describe('layout containment (#1169, #1176)', () => {
  it('Prepare preview scrolls inside a height-capped, container-query panel', () => {
    render(<PreviewPanel preview={preview} loading={false} />);
    expect(screen.getByTestId('preview-panel').className).toMatch(/max-h-\[60vh\]/);
    expect(screen.getByTestId('preview-panel').className).toMatch(/@3xl:w-96/);
    expect(screen.getByTestId('preview-scroll').className).toMatch(/overflow-auto/);
  });

  it('toolbar actions carry a name and a visible label', () => {
    const noop = jest.fn();
    render(
      <PipelineToolbar busy={false} onPreview={noop} onApply={noop} viewMode="chain" onViewChange={noop}
        onRecipes={noop} canUndo canRedo onUndo={noop} onRedo={noop} onExport={noop} />,
    );
    for (const name of ['Manage Recipes', 'Undo', 'Redo', 'Export as Code']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument();
    }
    expect(screen.getByText('Recipes').className).toMatch(/@3xl:inline/);
  });

  it('Explore data table scrolls inside its own capped container', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ data: [{ a: 1 }], total_rows: 1, columns: ['a'], offset: 0, rows: 1 }),
    });
    render(<DataPreviewTable datasetId="d1" onExport={jest.fn()} />);
    const box = await screen.findByTestId('preview-scroll');
    expect(box.className).toMatch(/overflow-auto/);
    expect(box.className).toMatch(/max-h-/);
  });
});
