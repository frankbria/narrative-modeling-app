import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { LineChart, LineChartData } from '@/components/LineChart'
import { axisTicks } from '@/__tests__/utils/sizedRecharts'

// Real recharts, with only ResponsiveContainer sized so jsdom's 0x0 layout
// doesn't blank the chart (#346) — so Line/XAxis/dataKey wiring is exercised
// for real. `Tooltip` stays stubbed: recharts resolves the active index from
// mouse geometry, which jsdom has none of, so a real hover never opens it. The
// stub reproduces v3's contract exactly — clone the `content` element and
// inject active/payload/label — which is what CustomTooltip depends on.
jest.mock('recharts', () => {
  const React = jest.requireActual('react')
  return {
    ...jest.requireActual('@/__tests__/utils/sizedRecharts').sizedRecharts(),
    Tooltip: ({ content }: { content?: React.ReactElement }) =>
      content
        ? React.cloneElement(content, {
            active: true,
            payload: [{ name: 'Sales', value: 150, color: '#000' }],
            label: '2024',
          })
        : null,
  }
})

const data: LineChartData = {
  data: [
    { x: '2023', sales: 100 },
    { x: '2024', sales: 150 },
  ],
  lines: [{ dataKey: 'sales', label: 'Sales' }],
  xLabel: 'Year',
  yLabel: 'Sales',
  title: 'Sales over time',
}

describe('LineChart', () => {
  it('renders the chart title', () => {
    render(<LineChart data={data} />)
    expect(screen.getByText('Sales over time')).toBeInTheDocument()
  })

  it('draws one line per series, x-labelled by the x dataKey', () => {
    const { container } = render(<LineChart data={data} />)

    expect(container.querySelectorAll('.recharts-line')).toHaveLength(1)
    expect(axisTicks(container, 'x')).toEqual(['2023', '2024'])
  })

  it('forwards recharts chart state to onPointClick when the chart is clicked', () => {
    const onPointClick = jest.fn()
    const { container } = render(
      <LineChart data={data} onPointClick={onPointClick} />
    )

    fireEvent.click(container.querySelector('.recharts-wrapper')!)

    // Real recharts drives this, so the adapter is verified against v3's actual
    // onClick signature. The state's *contents* are not asserted: recharts
    // derives the active index from mouse geometry and jsdom reports none, so
    // every field comes back null here regardless of the click position.
    expect(onPointClick).toHaveBeenCalledTimes(1)
    expect(onPointClick.mock.calls[0][0]).toEqual(expect.any(Object))
  })

  it('does not pass an onClick handler when onPointClick is omitted', () => {
    const { container } = render(<LineChart data={data} />)
    expect(() =>
      fireEvent.click(container.querySelector('.recharts-wrapper')!)
    ).not.toThrow()
  })

  it('renders the tooltip with xLabel threaded through as a prop', () => {
    // xLabel used to be closed over; after the module-scope lift (#373) it is a
    // prop on the element recharts clones. Nothing else asserts it arrives.
    render(<LineChart data={data} />)

    expect(screen.getByText('Year: 2024')).toBeInTheDocument()
    expect(screen.getByText('Sales: 150.00')).toBeInTheDocument()
  })
})

describe('axis title and legend do not collide (#404)', () => {
  // On /monitor the x-axis title ("Time") was drawn straight through the legend
  // row and the tick labels — all three landed in the same ~30px band. recharts
  // defaults the legend to `height: auto` at `bottom: <margin.bottom>`, i.e. right
  // where the axis title sits. LineChart now reserves an explicit legend band at
  // `bottom: 0`, which both separates them and makes the extents computable —
  // with `height: auto` there is nothing to assert against.
  const multi = {
    data: [
      { x: '11:50 PM', latency: 12, requests: 3 },
      { x: '02:50 AM', latency: 30, requests: 9 },
    ],
    lines: [
      { dataKey: 'latency', label: 'Avg Latency (ms)' },
      { dataKey: 'requests', label: 'Requests' },
    ],
    xLabel: 'Time',
    yLabel: 'Count / ms',
  }

  /** Approximate vertical extent of an SVG <text>, from its baseline. */
  const textBand = (el: Element) => {
    const y = Number(el.getAttribute('y'))
    return { top: y - 12, bottom: y + 4 }
  }

  it('the legend sits below the axis title, which sits below the ticks', () => {
    const { container } = render(<LineChart data={multi} />)

    const title = Array.from(container.querySelectorAll('text')).find(
      (t) => t.textContent === 'Time'
    )
    const tick = container.querySelector(
      '.recharts-xAxis-tick-labels .recharts-cartesian-axis-tick-value'
    )
    const legend = container.querySelector(
      '.recharts-legend-wrapper'
    ) as HTMLElement | null

    expect(title).toBeDefined()
    expect(tick).not.toBeNull()
    expect(legend).not.toBeNull()

    const chartHeight = 400 // the height sizedRecharts gives ResponsiveContainer
    const style = legend!.getAttribute('style') ?? ''
    const legendHeight = Number(/height:\s*(\d+)px/.exec(style)?.[1])
    const legendBottomOffset = Number(/bottom:\s*(\d+)px/.exec(style)?.[1])

    // `height: auto` would make this NaN — which is the state that made the
    // collision unassertable in the first place.
    expect(Number.isFinite(legendHeight)).toBe(true)
    expect(Number.isFinite(legendBottomOffset)).toBe(true)

    const legendTop = chartHeight - legendBottomOffset - legendHeight
    const titleBand = textBand(title!)
    const tickBand = textBand(tick!)

    expect(tickBand.bottom).toBeLessThan(titleBand.top)
    expect(titleBand.bottom).toBeLessThan(legendTop)
  })

  it('a single-series chart renders no legend to collide with', () => {
    const { container } = render(
      <LineChart data={{ ...multi, lines: [multi.lines[0]] }} />
    )
    expect(container.querySelector('.recharts-legend-wrapper')).toBeNull()
  })
})
