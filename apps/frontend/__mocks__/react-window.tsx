import React from 'react';

export const FixedSizeList = React.forwardRef<HTMLDivElement, any>(
  function MockFixedSizeList(
    { children, itemCount, itemSize, height, width, role },
    ref
  ) {
    // Handle both function children and component children
    const renderItem = (index: number) => {
      const style = { height: itemSize, top: index * itemSize };

      if (typeof children === 'function') {
        // Children is a render function
        return children({ index, style });
      } else {
        // Children is a component
        const ChildComponent = children;
        return <ChildComponent index={index} style={style} />;
      }
    };

    return (
      <div
        ref={ref}
        data-testid="virtual-list"
        style={{ height, width, overflow: 'auto' }}
        role={role || 'presentation'}
      >
        {Array.from({ length: Math.min(itemCount, 100) }).map((_, i) => (
          <div key={`item-${i}`}>
            {renderItem(i)}
          </div>
        ))}
      </div>
    );
  }
);

FixedSizeList.displayName = 'MockFixedSizeList';
