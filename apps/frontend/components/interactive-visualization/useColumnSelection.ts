import { useMemo, useState } from 'react';
import {
  columnsOfType,
  toggleColumn,
  withDefaultSelection,
  type DashboardColumn,
} from './chartSelection';

/**
 * The columns picked for the chart. Every list derived from the selection is
 * memoised because they feed the chart fetch's dependency list; a fresh array
 * per render would refetch forever.
 */
export function useColumnSelection(columns: DashboardColumn[], activeChart: string) {
  const [chosen, setChosen] = useState<string[]>([]);

  const numericColumns = useMemo(() => columnsOfType(columns, 'numeric'), [columns]);
  const numericNames = useMemo(
    () => new Set(numericColumns.map(col => col.name)),
    [numericColumns],
  );

  // Derived during render rather than written back by an effect: the default is
  // a function of the columns, so storing it only creates a second source of truth.
  const selectedColumns = useMemo(
    () => withDefaultSelection(chosen, numericColumns),
    [chosen, numericColumns],
  );
  const numericSelected = useMemo(
    () => selectedColumns.filter(name => numericNames.has(name)),
    [selectedColumns, numericNames],
  );

  // Line charts plot a numeric Y series against any-type X (e.g. a date), so
  // X is the first selected column and Y is the remaining numeric columns.
  const lineX = selectedColumns[0];
  const lineY = useMemo(
    () => selectedColumns.slice(1).filter(name => numericNames.has(name)),
    [selectedColumns, numericNames],
  );

  // Based on the derived selection, so un-picking the auto-selected column
  // behaves the way it did when that default was stored.
  const toggle = (columnName: string) =>
    setChosen(toggleColumn(selectedColumns, columnName, activeChart));

  return { selectedColumns, numericSelected, lineX, lineY, toggle };
}
