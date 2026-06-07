import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { InteractiveTutorial } from '@/components/InteractiveTutorial';

const steps = [
  {
    id: 'step-1',
    title: 'First step',
    description: 'desc',
    action: 'observe' as const,
    target: '#tutorial-target',
    content: 'Look at this element',
    tip: 'A helpful tip',
  },
  {
    id: 'step-2',
    title: 'Second step',
    description: 'desc',
    action: 'click' as const,
    content: 'Click the button',
  },
];

describe('InteractiveTutorial', () => {
  beforeEach(() => {
    const target = document.createElement('div');
    target.id = 'tutorial-target';
    document.body.appendChild(target);
  });

  afterEach(() => {
    document.getElementById('tutorial-target')?.remove();
  });

  // Regression: starting a tutorial whose first step has a `target` used to
  // crash because `setIsHighlighting` was called without the state being
  // declared. This verifies the highlighting flow renders without throwing.
  it('starts a tutorial with a highlighted target without crashing', () => {
    expect(() =>
      render(
        <InteractiveTutorial steps={steps} onComplete={() => {}} autoStart />
      )
    ).not.toThrow();

    // Active tutorial shows the step counter and the highlighting indicator.
    expect(screen.getByText('Step 1 of 2')).toBeInTheDocument();
    expect(screen.getByText('Highlighting')).toBeInTheDocument();
  });

  it('does not show the highlighting indicator before starting', () => {
    render(<InteractiveTutorial steps={steps} onComplete={() => {}} />);

    expect(screen.queryByText('Highlighting')).not.toBeInTheDocument();
    expect(screen.getByText('Interactive Tutorial')).toBeInTheDocument();
  });

  it('advances to the next step without throwing when removing the highlight', () => {
    render(<InteractiveTutorial steps={steps} onComplete={() => {}} autoStart />);

    // Advancing from a highlighted step calls removeHighlight() ->
    // setIsHighlighting(false). Verify this does not throw.
    const nextButton = screen.getByRole('button', { name: /next/i });
    expect(() => fireEvent.click(nextButton)).not.toThrow();

    expect(screen.getByText('Step 2 of 2')).toBeInTheDocument();
  });
});
