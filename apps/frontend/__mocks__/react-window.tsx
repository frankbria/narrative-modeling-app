import React from 'react';

export const FixedSizeList = React.forwardRef<HTMLDivElement, any>(
  function MockFixedSizeList(
    { children, itemCount, itemSize, height, width, role },
    ref
  ) {
    return (
      <div
        ref={ref}
        data-testid="virtual-list"
        style={{ height, width, overflow: 'auto' }}
        role={role || 'presentation'}
      >
        {Array.from({ length: Math.min(itemCount, 100) }).map((_, i) => (
          <div key={`item-${i}`}>
            {children({ index: i, style: { height: itemSize, top: i * itemSize } })}
          </div>
        ))}
      </div>
    );
  }
);

FixedSizeList.displayName = 'MockFixedSizeList';
