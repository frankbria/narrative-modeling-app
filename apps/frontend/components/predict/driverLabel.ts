/**
 * Plain-language names for what drove a prediction (#1170).
 *
 * The explanation names the model's engineered inputs, where a category is a
 * one-hot column called `<column>_<value>`. The raw columns are in the response's
 * `feature_names`, so the column and the value can be split apart again.
 */

export interface Driver {
  column: string;
  /** The category this input stands for; null for a plain numeric column. */
  value: string | null;
}

export function describeDriver(name: string, columns: string[]): Driver {
  if (columns.includes(name)) return { column: name, value: null };
  const owner = columns
    .filter((column) => name.startsWith(`${column}_`))
    .sort((a, b) => b.length - a.length)[0];
  return owner ? { column: owner, value: name.slice(owner.length + 1) } : { column: name, value: null };
}

/** "contract_type is Month-to-month"; a category the record did not have reads "is not". */
export function driverText(driver: Driver, featureValue: number | null | undefined): string {
  if (driver.value === null) return driver.column;
  return `${driver.column} ${featureValue === 0 ? 'is not' : 'is'} ${driver.value}`;
}
