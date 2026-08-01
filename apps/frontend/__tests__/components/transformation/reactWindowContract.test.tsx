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
 * jsdom has no layout, so `List` normally measures a zero-height container and
 * renders no rows — but passing `defaultHeight` (the SSR escape hatch) makes it
 * render them anyway, which lets the row-level `ariaAttributes` contract be
 * pinned against the real library too, not just the container.
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

/** Renders whatever the real library passes as `ariaAttributes` onto the row. */
function AriaProbeRow({ style, ariaAttributes }: RowComponentProps) {
  return (
    <div data-testid="probe-row" style={style} {...ariaAttributes}>
      row
    </div>
  );
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

  describe('row ariaAttributes', () => {
    // Both ColumnListItem components spread {...ariaAttributes} onto each row.
    // The mock fabricates that object, so without this the shape is only ever
    // asserted against the mock's own invention — the exact circularity this
    // PR exists to remove.
    function renderRows() {
      return render(
        <List
          rowComponent={AriaProbeRow}
          rowCount={5}
          rowHeight={10}
          rowProps={{}}
          defaultHeight={100}
        />
      );
    }

    it('supplies aria-posinset, aria-setsize and a listitem role per row', () => {
      const { container } = renderRows();

      const rows = container.querySelectorAll('[data-testid="probe-row"]');
      expect(rows.length).toBeGreaterThan(0);

      // 1-based position, total = rowCount, and the default role the components
      // deliberately override with role="option".
      expect(rows[0]).toHaveAttribute('aria-posinset', '1');
      expect(rows[0]).toHaveAttribute('aria-setsize', '5');
      expect(rows[0]).toHaveAttribute('role', 'listitem');
    });

    it('keeps aria-posinset in step with the row index', () => {
      const { container } = renderRows();

      const rows = [...container.querySelectorAll('[data-testid="probe-row"]')];
      rows.forEach((row, i) => {
        expect(row).toHaveAttribute('aria-posinset', String(i + 1));
      });
    });
  });
});
