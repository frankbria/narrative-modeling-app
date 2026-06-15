import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { TransformationPreview } from '@/components/transformation/TransformationPreview';
import type { TransformationStep } from '@/lib/types/recipe';

// Mock child components
jest.mock('@/components/transformation/BeforeAfterView', () => ({
  BeforeAfterView: jest.fn(({ originalData, transformedData }) => (
    <div data-testid="before-after-view">
      Before: {originalData.length} rows, After: {transformedData.length} rows
    </div>
  )),
}));

jest.mock('@/components/transformation/ImpactStats', () => ({
  ImpactStats: jest.fn(({ impactStats }) => (
    <div data-testid="impact-stats">
      Rows affected: {impactStats.rows_affected}
    </div>
  )),
}));

jest.mock('@/components/transformation/PreviewControls', () => ({
  PreviewControls: jest.fn(({ sampleSize, onSampleSizeChange, onRefresh, onExport, loading }) => (
    <div data-testid="preview-controls">
      <button onClick={() => onSampleSizeChange(500)}>Change Size</button>
      <button onClick={onRefresh} disabled={loading}>
        Refresh
      </button>
      <button onClick={onExport} disabled={loading || !onExport}>
        Export
      </button>
      <span>Sample: {sampleSize}</span>
    </div>
  )),
}));

// Mock debounce hook to skip delay in tests
jest.mock('@/lib/hooks/useDebounce', () => ({
  useDebounce: (value: any) => value,
}));

// Mock auth helpers
jest.mock('@/lib/auth-helpers', () => ({
  getAuthToken: jest.fn(() => Promise.resolve('mock-token')),
}));

// Mock fetch
global.fetch = jest.fn();

describe('TransformationPreview Component', () => {
  const mockOperations: TransformationStep[] = [
    {
      type: 'remove_nulls',
      parameters: { column: 'age' },
    },
  ];

  const mockPreviewResponse = {
    success: true,
    preview_result: {
      original_data: [
        { id: 1, name: 'Alice', age: null },
        { id: 2, name: 'Bob', age: 30 },
      ],
      transformed_data: [
        { id: 1, name: 'Alice', age: 0 },
        { id: 2, name: 'Bob', age: 30 },
      ],
      impact_stats: {
        rows_affected: 1,
        values_changed: 1,
        columns_affected: ['age'],
        quality_score_before: 0.5,
        quality_score_after: 1.0,
      },
      warnings: [],
    },
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => mockPreviewResponse,
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Loading State', () => {
    it('should display loading state while fetching preview', async () => {
      // Make fetch hang to keep loading state
      (global.fetch as jest.Mock).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Generating preview\.\.\./i)).toBeInTheDocument();
      });
    });

    it('should show spinner during loading', async () => {
      (global.fetch as jest.Mock).mockImplementation(
        () => new Promise(() => {})
      );

      const { container } = render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('should display error message when fetch fails', async () => {
      const errorMessage = 'Failed to generate preview';
      (global.fetch as jest.Mock).mockRejectedValue(new Error(errorMessage));

      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Preview Error/i)).toBeInTheDocument();
        expect(screen.getByText(errorMessage)).toBeInTheDocument();
      });
    });

    it('should display error when API returns error response', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'Dataset not found' }),
      });

      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Dataset not found')).toBeInTheDocument();
      });
    });

    it('should show retry button on error', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(
        new Error('Network error')
      );

      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        const retryButton = screen.getByText('Try again');
        expect(retryButton).toBeInTheDocument();
      });
    });

    it('should clear error when retry button clicked', async () => {
      // First call fails
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/Network error/i)).toBeInTheDocument();
      });

      const retryButton = screen.getByText('Try again');

      // Mock success for retry (though component implementation doesn't actually re-fetch on retry)
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockPreviewResponse,
      });

      fireEvent.click(retryButton);

      // Verify error is cleared
      await waitFor(() => {
        expect(screen.queryByText(/Network error/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Empty Operations', () => {
    it('should display message when operations array is empty', () => {
      render(
        <TransformationPreview datasetId="dataset123" operations={[]} />
      );

      expect(
        screen.getByText(/Add transformation operations to see a preview/i)
      ).toBeInTheDocument();
    });

    it('should not fetch preview when operations is empty', () => {
      render(
        <TransformationPreview datasetId="dataset123" operations={[]} />
      );

      expect(global.fetch).not.toHaveBeenCalled();
    });
  });

  describe('Successful Preview Display', () => {
    it('should render all child components on success', async () => {
      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('preview-controls')).toBeInTheDocument();
        expect(screen.getByTestId('impact-stats')).toBeInTheDocument();
        expect(screen.getByTestId('before-after-view')).toBeInTheDocument();
      });
    });

    it('should pass correct data to BeforeAfterView', async () => {
      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('before-after-view')).toHaveTextContent(
          'Before: 2 rows, After: 2 rows'
        );
      });
    });

    it('should pass correct stats to ImpactStats', async () => {
      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('impact-stats')).toHaveTextContent(
          'Rows affected: 1'
        );
      });
    });
  });

  describe('Warnings Display', () => {
    it('should display warnings when present in preview result', async () => {
      const responseWithWarnings = {
        ...mockPreviewResponse,
        preview_result: {
          ...mockPreviewResponse.preview_result,
          warnings: [
            'This transformation may affect data quality',
            'Consider reviewing affected columns',
          ],
        },
      };

      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => responseWithWarnings,
      });

      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(screen.getByText('Warnings')).toBeInTheDocument();
        expect(
          screen.getByText('This transformation may affect data quality')
        ).toBeInTheDocument();
        expect(
          screen.getByText('Consider reviewing affected columns')
        ).toBeInTheDocument();
      });
    });

    it('should not display warnings section when warnings array is empty', async () => {
      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('impact-stats')).toBeInTheDocument();
      });

      expect(screen.queryByText('Warnings')).not.toBeInTheDocument();
    });
  });

  describe('Sample Size Changes', () => {
    it('should trigger new preview when sample size changes', async () => {
      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
          sampleSize={100}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('preview-controls')).toBeInTheDocument();
      });

      // Initial fetch
      expect(global.fetch).toHaveBeenCalledTimes(1);

      // Change sample size
      const changeSizeButton = screen.getByText('Change Size');
      fireEvent.click(changeSizeButton);

      await waitFor(() => {
        // Second fetch with new sample size
        expect(global.fetch).toHaveBeenCalledTimes(2);
      });
    });

    it('should call onSampleSizeChange callback when sample size changes', async () => {
      const onSampleSizeChange = jest.fn();

      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
          sampleSize={100}
          onSampleSizeChange={onSampleSizeChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('preview-controls')).toBeInTheDocument();
      });

      const changeSizeButton = screen.getByText('Change Size');
      fireEvent.click(changeSizeButton);

      expect(onSampleSizeChange).toHaveBeenCalledWith(500);
    });
  });

  describe('Debounced Updates', () => {
    it('should use debounced operations value', async () => {
      const { rerender } = render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledTimes(1);
      });

      // Update operations
      const newOperations: TransformationStep[] = [
        ...mockOperations,
        { type: 'normalize', parameters: {} },
      ];

      rerender(
        <TransformationPreview
          datasetId="dataset123"
          operations={newOperations}
        />
      );

      // Since debounce is mocked to return value immediately, should trigger new fetch
      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledTimes(2);
      });
    });

    it('should include correct transformations in API call', async () => {
      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
          sampleSize={100}
        />
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/transformations/pipeline/preview'),
          expect.objectContaining({
            method: 'POST',
            headers: expect.objectContaining({
              'Content-Type': 'application/json',
              Authorization: 'Bearer mock-token',
            }),
            body: JSON.stringify({
              dataset_id: 'dataset123',
              transformations: [
                {
                  type: 'remove_nulls',
                  parameters: { column: 'age' },
                },
              ],
              sample_size: 100,
            }),
          })
        );
      });
    });
  });

  describe('CSV Export', () => {
    let createObjectURLSpy: jest.SpyInstance;
    let revokeObjectURLSpy: jest.SpyInstance;
    let clickSpy: jest.SpyInstance;
    let originalCreateObjectURL: typeof URL.createObjectURL;
    let originalRevokeObjectURL: typeof URL.revokeObjectURL;

    beforeEach(() => {
      originalCreateObjectURL = URL.createObjectURL;
      originalRevokeObjectURL = URL.revokeObjectURL;
      createObjectURLSpy = jest.fn(() => 'blob:mock-url');
      revokeObjectURLSpy = jest.fn();
      URL.createObjectURL = createObjectURLSpy as unknown as typeof URL.createObjectURL;
      URL.revokeObjectURL = revokeObjectURLSpy as unknown as typeof URL.revokeObjectURL;
      clickSpy = jest
        .spyOn(HTMLAnchorElement.prototype, 'click')
        .mockImplementation(() => {});
    });

    afterEach(() => {
      URL.createObjectURL = originalCreateObjectURL;
      URL.revokeObjectURL = originalRevokeObjectURL;
      clickSpy.mockRestore();
    });

    it('should disable export until preview data is available', async () => {
      (global.fetch as jest.Mock).mockImplementation(
        () => new Promise(() => {}) // never resolves -> no preview data
      );

      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      const exportButton = screen.getByText('Export').closest('button');
      expect(exportButton).toBeDisabled();
    });

    it('should enable export once preview data loads', async () => {
      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('before-after-view')).toBeInTheDocument();
      });

      const exportButton = screen.getByText('Export').closest('button');
      expect(exportButton).not.toBeDisabled();
    });

    it('should trigger a CSV download when export is clicked', async () => {
      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('before-after-view')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Export').closest('button')!);

      expect(createObjectURLSpy).toHaveBeenCalledTimes(1);
      const blobArg = createObjectURLSpy.mock.calls[0][0] as Blob;
      expect(blobArg).toBeInstanceOf(Blob);
      expect(blobArg.type).toBe('text/csv');
      expect(clickSpy).toHaveBeenCalledTimes(1);
      expect(revokeObjectURLSpy).toHaveBeenCalledWith('blob:mock-url');
    });

    it('serializes complex cell values as JSON and quotes them', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({
          success: true,
          preview_result: {
            original_data: [{ id: 1 }],
            transformed_data: [
              { id: 1, tags: ['x', 'y'], meta: { k: 'v' } },
            ],
            impact_stats: {
              rows_affected: 0,
              values_changed: 0,
              columns_affected: [],
              quality_score_before: 1,
              quality_score_after: 1,
            },
            warnings: [],
          },
        }),
      });

      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('before-after-view')).toBeInTheDocument();
      });

      const OriginalBlob = global.Blob;
      const blobSpy = jest
        .spyOn(global, 'Blob')
        .mockImplementation(
          (parts, opts) => new OriginalBlob(parts as BlobPart[], opts)
        );

      fireEvent.click(screen.getByText('Export').closest('button')!);

      const blobParts = blobSpy.mock.calls[0][0] as string[];
      const csv = blobParts.join('');

      expect(csv).toContain('id,tags,meta');
      // Arrays/objects are JSON-serialized; commas inside force RFC 4180 quoting.
      expect(csv).toContain('"[""x"",""y""]"');
      expect(csv).toContain('"{""k"":""v""}"');

      blobSpy.mockRestore();
    });
  });

  describe('API Integration', () => {
    it('should use correct API endpoint', async () => {
      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/transformations/pipeline/preview'),
          expect.any(Object)
        );
      });
    });

    it('should include authorization token in request', async () => {
      render(
        <TransformationPreview
          datasetId="dataset123"
          operations={mockOperations}
        />
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.any(String),
          expect.objectContaining({
            headers: expect.objectContaining({
              Authorization: 'Bearer mock-token',
            }),
          })
        );
      });
    });
  });
});
