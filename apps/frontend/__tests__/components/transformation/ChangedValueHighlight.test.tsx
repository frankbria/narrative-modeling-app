import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ChangedValueHighlight } from '@/components/transformation/ChangedValueHighlight';

describe('ChangedValueHighlight Component', () => {
  describe('Unchanged Value Display', () => {
    it('should display value without highlight when isChanged is false', () => {
      render(
        <ChangedValueHighlight
          value="test value"
          isChanged={false}
          oldValue="old value"
        />
      );

      const valueElement = screen.getByText('test value');
      expect(valueElement).toBeInTheDocument();
      expect(valueElement).toHaveClass('text-foreground');
      expect(valueElement).not.toHaveClass('bg-yellow-100');
    });

    it('should not show tooltip for unchanged values', () => {
      render(
        <ChangedValueHighlight
          value="unchanged"
          isChanged={false}
          oldValue="unchanged"
        />
      );

      expect(screen.queryByText(/Modified/i)).not.toBeInTheDocument();
    });

    it('should render simple span for unchanged values', () => {
      const { container } = render(
        <ChangedValueHighlight
          value="simple"
          isChanged={false}
        />
      );

      const span = container.querySelector('span');
      expect(span).toHaveClass('text-foreground');
      expect(span).not.toHaveClass('cursor-help');
    });
  });

  describe('Changed Value Highlight', () => {
    it('should apply yellow background when isChanged is true', () => {
      render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue="old value"
        />
      );

      const valueElement = screen.getByText('new value');
      expect(valueElement).toHaveClass('bg-yellow-100');
      expect(valueElement).toHaveClass('text-yellow-900');
    });

    it('should apply cursor-help class to changed values', () => {
      render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue="old value"
        />
      );

      const valueElement = screen.getByText('new value');
      expect(valueElement).toHaveClass('cursor-help');
    });

    it('should apply rounded styling to highlighted values', () => {
      render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue="old value"
        />
      );

      const valueElement = screen.getByText('new value');
      expect(valueElement).toHaveClass('rounded');
      expect(valueElement).toHaveClass('px-2');
      expect(valueElement).toHaveClass('py-1');
    });
  });

  describe('Tooltip Display', () => {
    it('should show tooltip on hover when value is changed', async () => {
      render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue="old value"
        />
      );

      const valueElement = screen.getByText('new value');
      fireEvent.mouseEnter(valueElement);

      await waitFor(() => {
        expect(screen.getByText('Modified')).toBeInTheDocument();
      });
    });

    it('should display old and new values in tooltip', async () => {
      render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue="old value"
        />
      );

      const valueElement = screen.getByText('new value');
      fireEvent.mouseEnter(valueElement);

      await waitFor(() => {
        expect(screen.getAllByText('old value').length).toBeGreaterThan(0);
        // 'new value' appears in both main display and tooltip
        expect(screen.getAllByText('new value').length).toBeGreaterThan(1);
      });
    });

    it('should hide tooltip on mouse leave', async () => {
      render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue="old value"
        />
      );

      const valueElement = screen.getByText('new value');
      fireEvent.mouseEnter(valueElement);

      await waitFor(() => {
        expect(screen.getByText('Modified')).toBeInTheDocument();
      });

      fireEvent.mouseLeave(valueElement);

      await waitFor(() => {
        expect(screen.queryByText('Modified')).not.toBeInTheDocument();
      });
    });

    it('should show arrow icon in tooltip', async () => {
      const { container } = render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue="old value"
        />
      );

      const valueElement = screen.getByText('new value');
      fireEvent.mouseEnter(valueElement);

      await waitFor(() => {
        const arrow = container.querySelector('svg');
        expect(arrow).toBeInTheDocument();
      });
    });
  });

  describe('Null Value Handling', () => {
    it('should display "(empty)" for null values', () => {
      render(
        <ChangedValueHighlight
          value={null}
          isChanged={false}
        />
      );

      expect(screen.getByText('(empty)')).toBeInTheDocument();
    });

    it('should display "(empty)" for undefined values', () => {
      render(
        <ChangedValueHighlight
          value={undefined}
          isChanged={false}
        />
      );

      expect(screen.getByText('(empty)')).toBeInTheDocument();
    });

    it('should show "(empty)" in tooltip for null old values', async () => {
      render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue={null}
        />
      );

      const valueElement = screen.getByText('new value');
      fireEvent.mouseEnter(valueElement);

      await waitFor(() => {
        expect(screen.getByText('Added')).toBeInTheDocument();
        expect(screen.getByText('(empty)')).toBeInTheDocument();
      });
    });

    it('should show "(empty)" in tooltip for null new values', async () => {
      render(
        <ChangedValueHighlight
          value={null}
          isChanged={true}
          oldValue="old value"
        />
      );

      const emptyElement = screen.getByText('(empty)');
      fireEvent.mouseEnter(emptyElement);

      await waitFor(() => {
        expect(screen.getByText('Removed')).toBeInTheDocument();
        expect(screen.getByText('old value')).toBeInTheDocument();
      });
    });
  });

  describe('Change Type Detection', () => {
    it('should detect "added" change type for null to value', async () => {
      render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue={null}
        />
      );

      const valueElement = screen.getByText('new value');
      fireEvent.mouseEnter(valueElement);

      await waitFor(() => {
        expect(screen.getByText('Added')).toBeInTheDocument();
      });
    });

    it('should detect "removed" change type for value to null', async () => {
      render(
        <ChangedValueHighlight
          value={null}
          isChanged={true}
          oldValue="old value"
        />
      );

      const emptyElement = screen.getByText('(empty)');
      fireEvent.mouseEnter(emptyElement);

      await waitFor(() => {
        expect(screen.getByText('Removed')).toBeInTheDocument();
      });
    });

    it('should detect "modified" change type for value to value', async () => {
      render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue="old value"
        />
      );

      const valueElement = screen.getByText('new value');
      fireEvent.mouseEnter(valueElement);

      await waitFor(() => {
        expect(screen.getByText('Modified')).toBeInTheDocument();
      });
    });

    it('should apply green background for added values', () => {
      render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue={null}
        />
      );

      const valueElement = screen.getByText('new value');
      expect(valueElement).toHaveClass('bg-green-100');
      expect(valueElement).toHaveClass('text-green-900');
    });

    it('should apply red background for removed values', () => {
      render(
        <ChangedValueHighlight
          value={null}
          isChanged={true}
          oldValue="old value"
        />
      );

      const emptyElement = screen.getByText('(empty)');
      expect(emptyElement).toHaveClass('bg-red-100');
      expect(emptyElement).toHaveClass('text-red-900');
    });

    it('should apply yellow background for modified values', () => {
      render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue="old value"
        />
      );

      const valueElement = screen.getByText('new value');
      expect(valueElement).toHaveClass('bg-yellow-100');
      expect(valueElement).toHaveClass('text-yellow-900');
    });
  });

  describe('Value Formatting', () => {
    it('should format boolean values as strings', () => {
      render(
        <ChangedValueHighlight
          value={true}
          isChanged={false}
        />
      );

      expect(screen.getByText('true')).toBeInTheDocument();
    });

    it('should format false boolean correctly', () => {
      render(
        <ChangedValueHighlight
          value={false}
          isChanged={false}
        />
      );

      expect(screen.getByText('false')).toBeInTheDocument();
    });

    it('should format numbers as strings', () => {
      render(
        <ChangedValueHighlight
          value={42}
          isChanged={false}
        />
      );

      expect(screen.getByText('42')).toBeInTheDocument();
    });

    it('should format objects as JSON strings', () => {
      const objValue = { key: 'value' };
      render(
        <ChangedValueHighlight
          value={objValue}
          isChanged={false}
        />
      );

      expect(screen.getByText('{"key":"value"}')).toBeInTheDocument();
    });

    it('should handle string values directly', () => {
      render(
        <ChangedValueHighlight
          value="string value"
          isChanged={false}
        />
      );

      expect(screen.getByText('string value')).toBeInTheDocument();
    });
  });

  describe('Tooltip Positioning', () => {
    it('should position tooltip above the value', async () => {
      const { container } = render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue="old value"
        />
      );

      const valueElement = screen.getByText('new value');
      fireEvent.mouseEnter(valueElement);

      await waitFor(() => {
        const tooltip = container.querySelector('.bottom-full');
        expect(tooltip).toBeInTheDocument();
      });
    });

    it('should have pointer-events-none on tooltip to prevent interference', async () => {
      const { container } = render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue="old value"
        />
      );

      const valueElement = screen.getByText('new value');
      fireEvent.mouseEnter(valueElement);

      await waitFor(() => {
        const tooltip = container.querySelector('.pointer-events-none');
        expect(tooltip).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('should have appropriate styling for focus states', () => {
      render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue="old value"
        />
      );

      const valueElement = screen.getByText('new value');
      expect(valueElement).toHaveClass('transition-all');
    });

    it('should use semantic HTML structure', () => {
      const { container } = render(
        <ChangedValueHighlight
          value="new value"
          isChanged={true}
          oldValue="old value"
        />
      );

      const wrapper = container.querySelector('.relative.inline-block');
      expect(wrapper).toBeInTheDocument();
    });
  });
});
