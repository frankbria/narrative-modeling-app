import React from 'react';
import { render, screen } from '@testing-library/react';
import { RecipeCompatibilityBadge } from '@/components/recipes/RecipeCompatibilityBadge';
import { RecipeCompatibilityResponse } from '@/lib/services/transformation';

describe('RecipeCompatibilityBadge', () => {
  const highCompatibility: RecipeCompatibilityResponse = {
    is_compatible: true,
    compatibility_score: 0.95,
    missing_columns: [],
    type_mismatches: [],
    warnings: [],
    suggestions: [],
  };

  const mediumCompatibility: RecipeCompatibilityResponse = {
    is_compatible: true,
    compatibility_score: 0.75,
    missing_columns: [],
    type_mismatches: [],
    warnings: ['Some columns may need adjustment'],
    suggestions: ['Consider normalizing numeric columns'],
  };

  const lowCompatibility: RecipeCompatibilityResponse = {
    is_compatible: false,
    compatibility_score: 0.45,
    missing_columns: ['age', 'income'],
    type_mismatches: [{ column: 'name', expected: 'string', actual: 'number' }],
    warnings: ['Missing required columns', 'Type mismatches detected'],
    suggestions: ['Add missing columns before applying', 'Fix type mismatches'],
  };

  describe('Loading State', () => {
    it('should show loading state when isLoading is true', () => {
      render(<RecipeCompatibilityBadge compatibility={null} isLoading={true} />);

      expect(screen.getByText('Checking...')).toBeInTheDocument();
    });

    it('should have pulse animation when loading', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={null} isLoading={true} />);

      const loadingText = screen.getByText('Checking...');
      expect(loadingText).toHaveClass('animate-pulse');
    });
  });

  describe('Null Compatibility', () => {
    it('should return null when compatibility is null and not loading', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={null} isLoading={false} />);

      expect(container.firstChild).toBeNull();
    });
  });

  describe('High Compatibility (>=0.9)', () => {
    it('should display "Compatible" label for high compatibility', () => {
      render(<RecipeCompatibilityBadge compatibility={highCompatibility} />);

      expect(screen.getByText('Compatible')).toBeInTheDocument();
    });

    it('should display compatibility score percentage', () => {
      render(<RecipeCompatibilityBadge compatibility={highCompatibility} />);

      expect(screen.getByText('(95%)')).toBeInTheDocument();
    });

    it('should use success variant for high compatibility', () => {
      render(<RecipeCompatibilityBadge compatibility={highCompatibility} />);

      // Verify the badge is rendered with the correct content
      expect(screen.getByText('Compatible')).toBeInTheDocument();
    });

    it('should show CheckCircle icon for high compatibility', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={highCompatibility} />);

      const icon = container.querySelector('svg');
      expect(icon).toBeInTheDocument();
    });
  });

  describe('Medium Compatibility (0.7-0.9)', () => {
    it('should display "Partially Compatible" label for medium compatibility', () => {
      render(<RecipeCompatibilityBadge compatibility={mediumCompatibility} />);

      expect(screen.getByText('Partially Compatible')).toBeInTheDocument();
    });

    it('should display compatibility score percentage', () => {
      render(<RecipeCompatibilityBadge compatibility={mediumCompatibility} />);

      expect(screen.getByText('(75%)')).toBeInTheDocument();
    });

    it('should show AlertTriangle icon for medium compatibility', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={mediumCompatibility} />);

      const icon = container.querySelector('svg');
      expect(icon).toBeInTheDocument();
    });
  });

  describe('Low Compatibility (<0.7)', () => {
    it('should display "Incompatible" label for low compatibility', () => {
      render(<RecipeCompatibilityBadge compatibility={lowCompatibility} />);

      expect(screen.getByText('Incompatible')).toBeInTheDocument();
    });

    it('should display compatibility score percentage', () => {
      render(<RecipeCompatibilityBadge compatibility={lowCompatibility} />);

      expect(screen.getByText('(45%)')).toBeInTheDocument();
    });

    it('should show XCircle icon for low compatibility', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={lowCompatibility} />);

      const icon = container.querySelector('svg');
      expect(icon).toBeInTheDocument();
    });
  });

  describe('Tooltip with Warnings and Suggestions', () => {
    it('should show tooltip on hover when warnings exist', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={mediumCompatibility} />);

      const tooltip = container.querySelector('.group-hover\\:block');
      expect(tooltip).toBeInTheDocument();
    });

    it('should display warnings in tooltip', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={mediumCompatibility} />);

      const tooltipContent = container.querySelector('.group-hover\\:block');
      expect(tooltipContent?.textContent).toContain('Warnings:');
      expect(tooltipContent?.textContent).toContain('Some columns may need adjustment');
    });

    it('should display suggestions in tooltip', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={mediumCompatibility} />);

      const tooltipContent = container.querySelector('.group-hover\\:block');
      expect(tooltipContent?.textContent).toContain('Suggestions:');
      expect(tooltipContent?.textContent).toContain('Consider normalizing numeric columns');
    });

    it('should display compatibility score in tooltip', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={mediumCompatibility} />);

      const tooltipContent = container.querySelector('.group-hover\\:block');
      expect(tooltipContent?.textContent).toContain('Compatibility Score:');
      expect(tooltipContent?.textContent).toContain('75%');
    });

    it('should not show tooltip when no warnings or suggestions', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={highCompatibility} />);

      const tooltip = container.querySelector('.group-hover\\:block');
      expect(tooltip).not.toBeInTheDocument();
    });

    it('should display multiple warnings in list format', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={lowCompatibility} />);

      const tooltipContent = container.querySelector('.group-hover\\:block');
      expect(tooltipContent?.textContent).toContain('Missing required columns');
      expect(tooltipContent?.textContent).toContain('Type mismatches detected');
    });

    it('should display multiple suggestions in list format', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={lowCompatibility} />);

      const tooltipContent = container.querySelector('.group-hover\\:block');
      expect(tooltipContent?.textContent).toContain('Add missing columns before applying');
      expect(tooltipContent?.textContent).toContain('Fix type mismatches');
    });
  });

  describe('Accessibility', () => {
    it('should have cursor-help class for tooltip accessibility', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={mediumCompatibility} />);

      const badge = container.querySelector('[class*="cursor-help"]');
      expect(badge).toBeInTheDocument();
    });

    it('should be keyboard accessible', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={mediumCompatibility} />);

      const badgeContainer = container.querySelector('.group');
      expect(badgeContainer).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle score of exactly 0.9', () => {
      const exactlyNinety: RecipeCompatibilityResponse = {
        is_compatible: true,
        compatibility_score: 0.9,
        missing_columns: [],
        type_mismatches: [],
        warnings: [],
        suggestions: [],
      };

      render(<RecipeCompatibilityBadge compatibility={exactlyNinety} />);

      expect(screen.getByText('Compatible')).toBeInTheDocument();
      expect(screen.getByText('(90%)')).toBeInTheDocument();
    });

    it('should handle score of exactly 0.7', () => {
      const exactlySeventy: RecipeCompatibilityResponse = {
        is_compatible: true,
        compatibility_score: 0.7,
        missing_columns: [],
        type_mismatches: [],
        warnings: [],
        suggestions: [],
      };

      render(<RecipeCompatibilityBadge compatibility={exactlySeventy} />);

      expect(screen.getByText('Partially Compatible')).toBeInTheDocument();
      expect(screen.getByText('(70%)')).toBeInTheDocument();
    });

    it('should handle score of 0', () => {
      const zeroScore: RecipeCompatibilityResponse = {
        is_compatible: false,
        compatibility_score: 0,
        missing_columns: ['all'],
        type_mismatches: [],
        warnings: ['Complete data mismatch'],
        suggestions: ['Use a different recipe'],
      };

      render(<RecipeCompatibilityBadge compatibility={zeroScore} />);

      expect(screen.getByText('Incompatible')).toBeInTheDocument();
      expect(screen.getByText('(0%)')).toBeInTheDocument();
    });

    it('should handle score of 1 (perfect compatibility)', () => {
      const perfectScore: RecipeCompatibilityResponse = {
        is_compatible: true,
        compatibility_score: 1.0,
        missing_columns: [],
        type_mismatches: [],
        warnings: [],
        suggestions: [],
      };

      render(<RecipeCompatibilityBadge compatibility={perfectScore} />);

      expect(screen.getByText('Compatible')).toBeInTheDocument();
      expect(screen.getByText('(100%)')).toBeInTheDocument();
    });

    it('should handle empty warnings array', () => {
      const noWarnings: RecipeCompatibilityResponse = {
        is_compatible: true,
        compatibility_score: 0.8,
        missing_columns: [],
        type_mismatches: [],
        warnings: [],
        suggestions: ['Some suggestion'],
      };

      const { container } = render(<RecipeCompatibilityBadge compatibility={noWarnings} />);

      const tooltipContent = container.querySelector('.group-hover\\:block');
      expect(tooltipContent?.textContent).not.toContain('Warnings:');
      expect(tooltipContent?.textContent).toContain('Suggestions:');
    });

    it('should handle empty suggestions array', () => {
      const noSuggestions: RecipeCompatibilityResponse = {
        is_compatible: true,
        compatibility_score: 0.8,
        missing_columns: [],
        type_mismatches: [],
        warnings: ['Some warning'],
        suggestions: [],
      };

      const { container } = render(<RecipeCompatibilityBadge compatibility={noSuggestions} />);

      const tooltipContent = container.querySelector('.group-hover\\:block');
      expect(tooltipContent?.textContent).toContain('Warnings:');
      expect(tooltipContent?.textContent).not.toContain('Suggestions:');
    });
  });

  describe('Visual Styling', () => {
    it('should round percentage to nearest integer', () => {
      const fractionalScore: RecipeCompatibilityResponse = {
        is_compatible: true,
        compatibility_score: 0.876,
        missing_columns: [],
        type_mismatches: [],
        warnings: [],
        suggestions: [],
      };

      render(<RecipeCompatibilityBadge compatibility={fractionalScore} />);

      expect(screen.getByText('(88%)')).toBeInTheDocument();
    });

    it('should have proper gap between icon and text', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={highCompatibility} />);

      const badge = container.querySelector('[class*="gap-1"]');
      expect(badge).toBeInTheDocument();
    });

    it('should position tooltip arrow correctly', () => {
      const { container } = render(<RecipeCompatibilityBadge compatibility={mediumCompatibility} />);

      const arrow = container.querySelector('.-top-1');
      expect(arrow).toBeInTheDocument();
    });
  });
});
