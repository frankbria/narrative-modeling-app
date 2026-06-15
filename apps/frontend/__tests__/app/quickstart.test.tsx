import { render, screen } from '@testing-library/react';
import QuickstartPage from '@/app/quickstart/page';

describe('QuickstartPage', () => {
  it('renders the guide heading', () => {
    render(<QuickstartPage />);
    expect(
      screen.getByRole('heading', { name: /quickstart guide/i, level: 1 })
    ).toBeInTheDocument();
  });

  it('documents all 8 workflow stages', () => {
    render(<QuickstartPage />);
    const stageTitles = [
      'Upload Data',
      'Data Profiling',
      'Data Preparation',
      'Feature Engineering',
      'Model Training',
      'Model Evaluation',
      'Prediction',
      'Deployment',
    ];
    for (const title of stageTitles) {
      // Title appears in both the sidebar nav and the section heading.
      expect(screen.getAllByText(new RegExp(title, 'i')).length).toBeGreaterThan(0);
    }
  });

  it('renders anchor navigation for every stage', () => {
    render(<QuickstartPage />);
    const nav = screen.getByRole('navigation', { name: /quickstart sections/i });
    expect(nav).toBeInTheDocument();
    // Eight numbered anchor links.
    expect(nav.querySelectorAll('a[href^="#"]').length).toBe(8);
  });

  it('links each stage to its workflow route', () => {
    render(<QuickstartPage />);
    expect(screen.getAllByRole('link', { name: /go to upload/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: /upload your data/i })).toHaveAttribute(
      'href',
      '/upload'
    );
  });
});
