import React from 'react'

/**
 * Real recharts with **only** `ResponsiveContainer` replaced by a fixed-size wrapper.
 *
 * jsdom lays everything out as 0x0, so recharts' real `ResponsiveContainer` measures
 * zero and renders an empty div — which is why the chart suites historically mocked
 * every recharts primitive as a prop-ignoring passthrough. Those mocks are blind to
 * the library: after the recharts 2 -> 3 major (#346) they would render happily
 * against props v3 no longer accepts, exactly the failure mode #390 hit with
 * react-window. Stubbing the container alone keeps `Line`/`Bar`/`XAxis`/`Tooltip`
 * and the whole dataKey -> SVG pipeline real, so a signature change turns the suite
 * red instead of passing through.
 *
 * Usage (jest.mock factories can't close over outer scope, hence requireActual):
 *
 *     jest.mock('recharts', () =>
 *       jest.requireActual('@/__tests__/utils/sizedRecharts').sizedRecharts()
 *     )
 */
export function sizedRecharts(width = 800, height = 400) {
  const actual = jest.requireActual('recharts')

  const ResponsiveContainer = ({
    children,
  }: {
    children?: React.ReactNode
  }) =>
    React.isValidElement(children)
      ? React.cloneElement(children as React.ReactElement<Record<string, unknown>>, {
          width,
          height,
        })
      : children

  return { ...actual, ResponsiveContainer }
}

/**
 * Text of the rendered tick labels on one axis, in document order.
 *
 * recharts 3 hoists tick labels into their own z-index layer instead of nesting
 * them under the axis group, so they are addressed by `recharts-{x,y}Axis-tick-labels`
 * rather than by descending from `.recharts-xAxis`.
 */
export function axisTicks(container: HTMLElement, axis: 'x' | 'y'): string[] {
  return Array.from(
    container.querySelectorAll(
      `.recharts-${axis}Axis-tick-labels .recharts-cartesian-axis-tick-value`
    )
  ).map((el) => el.textContent ?? '')
}
