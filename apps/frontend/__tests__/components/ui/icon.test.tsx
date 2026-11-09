import { render, screen } from '@testing-library/react';
import { UserGroupIcon } from '@hugeicons/core-free-icons';
import { HugeiconsIcon } from '@/components/ui/icon';

describe('HugeiconsIcon', () => {
  it('hides a decorative icon from assistive tech', () => {
    const { container } = render(<HugeiconsIcon icon={UserGroupIcon} />);
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  it('exposes an icon that carries its own label', () => {
    render(<HugeiconsIcon icon={UserGroupIcon} aria-label="Public recipe" />);
    expect(screen.getByLabelText('Public recipe')).toHaveAttribute('aria-hidden', 'false');
  });
});
