import React from 'react';
import { render, screen } from '@testing-library/react';
import { axe } from 'jest-axe';
import { BoxplotChart } from '@/components/BoxplotChart';
import { CorrelationHeatmap } from '@/components/CorrelationHeatmap';
import type { BoxPlotData } from '@/lib/services/visualization';
import type { StatItem } from '@/lib/utils';

// Accessibility smoke tests for the pure-SVG charts (issue #282). ROC/PR curves
// use recharts (mocked in their own specs); their role="img" wrapper is asserted
// in ROCCurveChart.test.tsx / PRCurveChart.test.tsx.

const boxData: BoxPlotData = {
  min: 1,
  q1: 3,
  median: 5,
  q3: 7,
  max: 9,
  outliers: [12, -2],
};

const matrix: Record<string, Record<string, number>> = {
  age: { age: 1, income: 0.82, score: -0.4 },
  income: { age: 0.82, income: 1, score: 0.1 },
  score: { age: -0.4, income: 0.1, score: 1 },
};

const stats: StatItem[] = [];

describe('chart accessibility (issue #282)', () => {
  it('BoxplotChart has a role=img summary and no axe violations', async () => {
    const { container } = render(<BoxplotChart data={boxData} />);
    const img = screen.getByRole('img');
    expect(img).toHaveAttribute('aria-label', expect.stringContaining('median 5'));
    expect(await axe(container)).toHaveNoViolations();
  });

  it('BoxplotChart summarizes the outlier count', () => {
    render(<BoxplotChart data={boxData} />);
    expect(screen.getByRole('img').getAttribute('aria-label')).toContain('2 outliers');
  });

  it('CorrelationHeatmap has a role=img summary naming the strongest pair', async () => {
    const { container } = render(
      <CorrelationHeatmap stats={stats} correlationMatrix={matrix} />
    );
    const img = screen.getByRole('img');
    const label = img.getAttribute('aria-label') || '';
    expect(label).toContain('blue');
    expect(label).toContain('red');
    // Strongest off-diagonal correlation is age/income at 0.82.
    expect(label).toContain('0.82');
    expect(await axe(container)).toHaveNoViolations();
  });

  it('CorrelationHeatmap does not use a red/green color scale', () => {
    const { container } = render(
      <CorrelationHeatmap stats={stats} correlationMatrix={matrix} />
    );
    const fills = Array.from(container.querySelectorAll('rect'))
      .map((r) => r.getAttribute('fill') || '')
      .filter((f) => f.startsWith('hsl'));
    // Positive => red hue 0, negative => blue hue 220. Green (hue ~120) is gone.
    expect(fills.some((f) => f.includes('hsl(120'))).toBe(false);
    expect(fills.some((f) => f.startsWith('hsl(0') || f.startsWith('hsl(220'))).toBe(true);
  });
});
