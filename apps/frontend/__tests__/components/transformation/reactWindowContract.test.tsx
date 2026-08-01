/**
 * Contract test against the REAL react-window, not `__mocks__/react-window.tsx`.
 *
 * `ColumnSelector` and `BulkColumnSelector` depend on two behaviours of v2's
 * `List` that are NOT part of its documented public API:
 *
 *   1. it renders its container with a hard-coded `role="list"`, and
 *   2. it spreads caller props AFTER that role, so a caller-supplied `role`
 *      overrides it.
 *
 * Both components rely on (2) to neutralise (1) with `role="presentation"`,
 * because otherwise the DOM is `listbox > list > option` — invalid in both
 * directions. If a future react-window release changes either behaviour, the
 * components silently regress: there is no type error to catch it, and every
 * other test in the suite goes through the mock, which cannot notice.
 *
 * That is precisely the failure this PR (#390) was about — a mock that quietly
 * diverged from the real library and turned a broken component green. So the
 * assumption is pinned here against the real thing.
 *
 * jsdom has no layout, so `List` measures a zero-height container and renders
 * no rows. That is fine: this asserts the *container*, which renders regardless.
 */
jest.unmock('react-window');

import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import { List, type RowComponentProps } from 'react-window';

// Typed via RowComponentProps so the empty `rowProps={{}}` below type-checks —
// List infers its RowProps parameter from the row component's props.
function Row({ style }: RowComponentProps) {
  return <div style={style}>row</div>;
}

describe('react-window v2 contract (#390)', () => {
  it('is the real module, not the manual mock', () => {
    // The mock renders data-testid="virtual-list"; the real one does not.
    const { container } = render(
      <List rowComponent={Row} rowCount={3} rowHeight={10} rowProps={{}} />
    );
    expect(container.querySelector('[data-testid="virtual-list"]')).toBeNull();
  });

  it('defaults its container to role="list"', () => {
    const { container } = render(
      <List rowComponent={Row} rowCount={3} rowHeight={10} rowProps={{}} />
    );
    // If this fails, the components' role="presentation" is now papering over
    // nothing — re-check whether it is still needed.
    expect(container.firstElementChild).toHaveAttribute('role', 'list');
  });

  it('lets a caller-supplied role override that default', () => {
    const { container } = render(
      <List
        role="presentation"
        rowComponent={Row}
        rowCount={3}
        rowHeight={10}
        rowProps={{}}
      />
    );
    // If this fails, ColumnSelector/BulkColumnSelector are emitting
    // listbox > list > option again and their ARIA tests are only passing
    // because the mock is more permissive than the real library.
    expect(container.firstElementChild).toHaveAttribute('role', 'presentation');
  });

  it('spreads other caller aria-* props onto the container', () => {
    const { container } = render(
      <List
        role="presentation"
        aria-label="columns"
        rowComponent={Row}
        rowCount={3}
        rowHeight={10}
        rowProps={{}}
      />
    );
    expect(container.firstElementChild).toHaveAttribute('aria-label', 'columns');
  });
});
