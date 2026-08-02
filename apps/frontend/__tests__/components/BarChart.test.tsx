import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { BarChart, BarChartData } from '@/components/BarChart'
import { axisTicks } from '@/__tests__/utils/sizedRecharts'

// Real recharts, with only ResponsiveContainer sized so jsdom's 0x0 layout
// doesn't blank the chart (#346) -- so Bar/XAxis/dataKey wiring is exercised
// for real. `Tooltip` stays stubbed: recharts resolves the active index from
// mouse geometry, which jsdom has none of, so a real hover never opens it. The
// stub reproduces v3's contract exactly -- clone the `content` element and
// inject active/payload/label -- which is what CustomTooltip depends on.
jest.mock('recharts', () => {
  const React = jest.requireActual('react')
  return {
    ...jest.requireActual('@/__tests__/utils/sizedRecharts').sizedRecharts(),
    Tooltip: ({ content }: { content?: React.ReactElement }) =>
      content
        ? React.cloneElement(content, {
            active: true,
            payload: [{ value: 30, color: '#000' }],
            label: 'B',
          })
        : null,
  }
})

const data: BarChartData = {
  data: [
    { category: 'A', value: 10 },
    { category: 'B', value: 30 },
    { category: 'C', value: 20 },
  ],
  xLabel: 'Category',
  yLabel: 'Count',
  sortBy: 'value',
}

describe('BarChart', () => {
  it('renders the summary stats from the supplied data', () => {
    render(<BarChart data={data} />)

    expect(screen.getByText('Categories')).toBeInTheDocument()
    // total = 60, categories = 3, average = 20
    expect(screen.getByText('60')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('20.0')).toBeInTheDocument()
  })

  it('draws horizontal bars when orientation is horizontal', () => {
    // The horizontal branch puts the numeric axis on X and the category axis on
    // Y, which recharts only honours when the chart itself is laid out
    // vertically. Without that, every bar has zero extent and the chart renders
    // empty while the summary stats below it still read correctly -- which is
    // how this shipped (found rendering the monitor Distribution tab, #346).
    const { container } = render(
      <BarChart data={data} orientation="horizontal" />
    )

    expect(container.querySelectorAll('.recharts-bar-rectangle')).toHaveLength(3)
    // Categories on the y-axis, counts on the x-axis.
    expect(axisTicks(container, 'y')).toEqual(['B', 'C', 'A'])
    expect(axisTicks(container, 'x').at(-1)).not.toBe('0')
  })

  it('draws one bar per row, x-labelled by the category dataKey', () => {
    const { container } = render(<BarChart data={data} />)

    expect(container.querySelectorAll('.recharts-bar-rectangle')).toHaveLength(3)
    // sortBy: 'value' -> descending, so B(30), C(20), A(10).
    expect(axisTicks(container, 'x')).toEqual(['B', 'C', 'A'])
  })

  it('forwards recharts chart state to onBarClick when the chart is clicked', () => {
    const onBarClick = jest.fn()
    const { container } = render(
      <BarChart data={data} onBarClick={onBarClick} />
    )

    fireEvent.click(container.querySelector('.recharts-wrapper')!)

    // Real recharts drives this, so the adapter is verified against v3's actual
    // onClick signature. The state's *contents* are not asserted: recharts
    // derives the active index from mouse geometry and jsdom reports none, so
    // every field comes back null here regardless of the click position.
    expect(onBarClick).toHaveBeenCalledTimes(1)
    expect(onBarClick.mock.calls[0][0]).toEqual(expect.any(Object))
  })

  it('does not pass an onClick handler when onBarClick is omitted', () => {
    // No handler provided → adapter is undefined; clicking is a no-op (no throw).
    const { container } = render(<BarChart data={data} />)
    expect(() =>
      fireEvent.click(container.querySelector('.recharts-wrapper')!)
    ).not.toThrow()
  })

  // CustomTooltip moved to module scope in #373, so the values it used to close
  // over are threaded through as props. These assert that threading, and the
  // zero-total guard the move made necessary.
  describe('tooltip', () => {
    it('renders yLabel and the percentage of total from its props', () => {
      render(<BarChart data={{ ...data, showPercentages: true }} />)

      // total = 60, payload value = 30 → 50.0%
      expect(screen.getByText('Count: 30')).toBeInTheDocument()
      expect(screen.getByText('50.0% of total')).toBeInTheDocument()
    })

    it('omits the percentage line when showPercentages is not set', () => {
      render(<BarChart data={data} />)

      expect(screen.getByText('Count: 30')).toBeInTheDocument()
      expect(screen.queryByText(/% of total/)).not.toBeInTheDocument()
    })

    it('renders 0.0% rather than NaN% when every value is zero', () => {
      // total === 0 used to divide by zero and print "NaN% of total".
      const zeroData: BarChartData = {
        ...data,
        data: [
          { category: 'A', value: 0 },
          { category: 'B', value: 0 },
        ],
        showPercentages: true,
      }
      render(<BarChart data={zeroData} />)

      expect(screen.getByText('0.0% of total')).toBeInTheDocument()
      expect(screen.queryByText(/NaN/)).not.toBeInTheDocument()
    })
  })
})
