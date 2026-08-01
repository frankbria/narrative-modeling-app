import React from 'react';

/**
 * Manual mock for react-window, applied automatically to every suite because
 * this directory sits next to node_modules (jest auto-mocks node modules found
 * in a root __mocks__ folder — no jest.mock() call needed).
 *
 * It exists because jsdom has no layout, so the real List measures a zero-height
 * container and renders no rows, which would make every row assertion fail. The
 * mock renders a bounded window of rows eagerly instead.
 *
 * It must track the real v2 prop contract. A mock that keeps accepting the v1
 * shape does not fail loudly when the component is wrong — it silently renders
 * from props the real List ignores, turning a broken component into a green
 * suite. That is exactly what happened before the v2 migration (#390): the old
 * mock exported `FixedSizeList` with itemCount/itemSize/children, so tests kept
 * passing against components the real library could not render.
 */
export const List = React.forwardRef<
  HTMLDivElement,
  {
    rowComponent: React.ComponentType<Record<string, unknown>>;
    rowCount: number;
    rowHeight: number | string;
    rowProps: Record<string, unknown>;
    className?: string;
    style?: React.CSSProperties;
    role?: string;
  } & React.HTMLAttributes<HTMLDivElement>
>(function MockList(
  { rowComponent: RowComponent, rowCount, rowHeight, rowProps, className, style, role, ...rest },
  ref
) {
  // Fail loudly rather than render nothing if a caller is still on the v1 API.
  if (typeof RowComponent !== 'function') {
    throw new Error(
      'react-window mock: `rowComponent` must be a function component. ' +
        'react-window v2 replaced children-as-function with the rowComponent prop.'
    );
  }
  if (typeof rowCount !== 'number') {
    throw new Error('react-window mock: `rowCount` is required (v1 called it itemCount).');
  }
  if (typeof rowHeight !== 'number' && typeof rowHeight !== 'string') {
    throw new Error('react-window mock: `rowHeight` is required (v1 called it itemSize).');
  }

  const height = typeof rowHeight === 'number' ? rowHeight : 0;

  return (
    <div
      ref={ref}
      // Real v2 spreads every remaining caller prop onto its container, so the
      // mock must too — otherwise attributes like aria-multiselectable silently
      // vanish in tests while working in production (or vice versa).
      {...rest}
      data-testid="virtual-list"
      className={className}
      style={{ overflow: 'auto', ...style }}
      // The real v2 List hard-codes role="list" on its container and spreads
      // caller props after it. Defaulting to "presentation" here would hide ARIA
      // nesting bugs that ship in production — which is exactly what happened:
      // the listbox > list > option regression this mock now exposes was
      // invisible while it rendered role="presentation".
      role={role || 'list'}
    >
      {/* Caps rendered rows at 100 — carried over from the v1 mock. Real
          virtualization renders only what fits the viewport, so this keeps
          jsdom cheap, but a suite with >100 rows silently gets partial
          coverage. Raise it deliberately if a fixture ever grows past 100. */}
      {Array.from({ length: Math.min(rowCount, 100) }).map((_, index) => (
        <RowComponent
          key={`row-${index}`}
          index={index}
          style={{ height, top: index * height }}
          ariaAttributes={{
            'aria-posinset': index + 1,
            'aria-setsize': rowCount,
            role: 'listitem',
          }}
          {...rowProps}
        />
      ))}
    </div>
  );
});

List.displayName = 'MockList';
