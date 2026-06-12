import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ConfusionMatrixChart } from '@/components/ConfusionMatrixChart'
import type { ConfusionMatrixData } from '@/lib/types/evaluation'

const data: ConfusionMatrixData = {
  labels: ['yes', 'no'],
  // Row "yes": 44 correct, 6 predicted as "no" (row total 50).
  // Row "no": 5 predicted as "yes", 65 correct (row total 70).
  matrix: [
    [44, 6],
    [5, 65],
  ],
}

describe('ConfusionMatrixChart', () => {
  it('renders a focusable cell per matrix entry with counts', () => {
    render(<ConfusionMatrixChart data={data} />)

    const cells = screen.getAllByRole('button')
    expect(cells).toHaveLength(4)
    cells.forEach((cell) => expect(cell).toHaveAttribute('tabindex', '0'))

    expect(
      screen.getByRole('button', { name: /actual yes, predicted yes: 44/i })
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /actual no, predicted yes: 5/i })
    ).toBeInTheDocument()
  })

  it('invokes onCellClick with actual, predicted and count when a cell is clicked', () => {
    const onCellClick = jest.fn()
    render(<ConfusionMatrixChart data={data} onCellClick={onCellClick} />)

    fireEvent.click(
      screen.getByRole('button', { name: /actual yes, predicted no: 6/i })
    )

    expect(onCellClick).toHaveBeenCalledTimes(1)
    expect(onCellClick).toHaveBeenCalledWith('yes', 'no', 6)
  })

  it('shows a detail panel with count and row percentage when a cell is selected', () => {
    render(<ConfusionMatrixChart data={data} />)

    expect(screen.queryByTestId('confusion-cell-detail')).not.toBeInTheDocument()

    fireEvent.click(
      screen.getByRole('button', { name: /actual yes, predicted no: 6/i })
    )

    const panel = screen.getByTestId('confusion-cell-detail')
    expect(panel).toBeInTheDocument()
    // 6 of 50 actual "yes" rows = 12.0%
    expect(panel).toHaveTextContent('yes')
    expect(panel).toHaveTextContent('no')
    expect(panel).toHaveTextContent('6')
    expect(panel).toHaveTextContent('12.0%')
  })

  it('selects a cell with the Enter key', () => {
    const onCellClick = jest.fn()
    render(<ConfusionMatrixChart data={data} onCellClick={onCellClick} />)

    const cell = screen.getByRole('button', { name: /actual no, predicted no: 65/i })
    fireEvent.keyDown(cell, { key: 'Enter' })

    expect(onCellClick).toHaveBeenCalledWith('no', 'no', 65)
    expect(screen.getByTestId('confusion-cell-detail')).toBeInTheDocument()
  })

  it('updates the detail panel when a different cell is selected', () => {
    render(<ConfusionMatrixChart data={data} />)

    fireEvent.click(
      screen.getByRole('button', { name: /actual yes, predicted no: 6/i })
    )
    fireEvent.click(
      screen.getByRole('button', { name: /actual no, predicted no: 65/i })
    )

    const panel = screen.getByTestId('confusion-cell-detail')
    expect(panel).toHaveTextContent('65')
    // 65 of 70 actual "no" rows = 92.9%
    expect(panel).toHaveTextContent('92.9%')
  })

  it('renders a friendly placeholder when there is no matrix data', () => {
    render(<ConfusionMatrixChart data={{ labels: [], matrix: [] }} />)

    expect(screen.getByText(/no confusion matrix data/i)).toBeInTheDocument()
    expect(screen.queryAllByRole('button')).toHaveLength(0)
  })
})
