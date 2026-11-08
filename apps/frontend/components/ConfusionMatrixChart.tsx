'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'
import type { ConfusionMatrixData } from '@/lib/types/evaluation'
import { confusionReading } from '@/components/evaluate/evaluationReading'

export interface ConfusionMatrixChartProps {
  data: ConfusionMatrixData
  onCellClick?: (actual: string, predicted: string, count: number) => void
}

interface SelectedCell {
  row: number
  col: number
}

/**
 * Interactive confusion-matrix heatmap (issue #79).
 *
 * SVG grid following the CorrelationHeatmap precedent: responsive sizing via
 * ResizeObserver, theme-token ramp with intensity normalized by the actual-class
 * (row) total. Correct predictions (diagonal) use primary, errors destructive. Cells are keyboard-focusable; clicking (or pressing Enter/Space)
 * selects a cell and shows a drill-down detail panel below the grid.
 */
export function ConfusionMatrixChart({ data, onCellClick }: ConfusionMatrixChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)
  const [selected, setSelected] = useState<SelectedCell | null>(null)

  useEffect(() => {
    const node = containerRef.current
    if (!node) return

    const updateWidth = () => setContainerWidth(node.clientWidth)
    updateWidth()

    const observer = new ResizeObserver(updateWidth)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  const rowTotals = useMemo(
    () => data.matrix.map((row) => row.reduce((sum, count) => sum + count, 0)),
    [data.matrix]
  )

  const numLabels = data.labels.length
  if (numLabels === 0 || data.matrix.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 bg-muted rounded-lg border border-border">
        <p className="text-muted-foreground">No confusion matrix data available</p>
      </div>
    )
  }

  const rowPercent = (row: number, count: number): number =>
    rowTotals[row] > 0 ? (count / rowTotals[row]) * 100 : 0

  // Light ramp: the fill never gets dark enough to hide the foreground text.
  const heatOpacity = (row: number, count: number) =>
    0.06 + (rowTotals[row] > 0 ? count / rowTotals[row] : 0) * 0.34

  const handleSelect = (row: number, col: number) => {
    setSelected({ row, col })
    onCellClick?.(data.labels[row], data.labels[col], data.matrix[row][col])
  }

  // Layout: minimum readable cell size, scaled up to fill the container.
  const minCellSize = 56
  const labelWidth = 110
  const labelHeight = 70
  const padding = 16
  const availableWidth = Math.max(
    containerWidth,
    minCellSize * numLabels + labelWidth + padding * 2
  )
  const cellSize = Math.max(
    minCellSize,
    (availableWidth - labelWidth - padding * 2) / numLabels
  )
  const width = numLabels * cellSize + labelWidth + padding * 2
  const height = numLabels * cellSize + labelHeight + padding * 2

  const selectedCount =
    selected !== null ? data.matrix[selected.row][selected.col] : 0

  return (
    <div className="w-full" data-testid="confusion-matrix">
      <div ref={containerRef} className="w-full overflow-x-auto">
        <svg
          width="100%"
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label="Confusion matrix"
        >
          <g transform={`translate(${labelWidth + padding}, ${labelHeight + padding})`}>
            {/* Axis titles */}
            <text
              x={(numLabels * cellSize) / 2}
              y={-labelHeight + 12}
              textAnchor="middle"
              className="text-xs font-semibold fill-foreground"
            >
              Predicted
            </text>
            <text
              transform={`translate(${-labelWidth + 12}, ${(numLabels * cellSize) / 2}) rotate(-90)`}
              textAnchor="middle"
              className="text-xs font-semibold fill-foreground"
            >
              Actual
            </text>

            {/* Column (predicted) labels */}
            {data.labels.map((label, j) => (
              <text
                key={`col-${label}`}
                x={j * cellSize + cellSize / 2}
                y={-10}
                textAnchor="middle"
                className="text-xs font-medium fill-foreground"
              >
                {label}
              </text>
            ))}

            {/* Row (actual) labels */}
            {data.labels.map((label, i) => (
              <text
                key={`row-${label}`}
                x={-10}
                y={i * cellSize + cellSize / 2}
                textAnchor="end"
                dominantBaseline="middle"
                className="text-xs font-medium fill-foreground"
              >
                {label}
              </text>
            ))}

            {/* Cells */}
            {data.matrix.map((row, i) =>
              row.map((count, j) => {
                const pct = rowPercent(i, count)
                const isSelected = selected?.row === i && selected?.col === j
                const label = `Actual ${data.labels[i]}, predicted ${data.labels[j]}: ${count} (${pct.toFixed(1)}% of ${data.labels[i]})`
                return (
                  <g
                    key={`cell-${i}-${j}`}
                    role="button"
                    tabIndex={0}
                    aria-label={label}
                    aria-pressed={isSelected}
                    className="cursor-pointer focus:outline-none"
                    onClick={() => handleSelect(i, j)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        handleSelect(i, j)
                      }
                    }}
                  >
                    <title>{`${count} (${pct.toFixed(1)}% of ${data.labels[i]})`}</title>
                    <rect
                      x={j * cellSize}
                      y={i * cellSize}
                      width={cellSize}
                      height={cellSize}
                      fill={i === j ? 'var(--primary)' : 'var(--destructive)'}
                      fillOpacity={heatOpacity(i, count)}
                      stroke={isSelected ? 'var(--primary)' : 'var(--card)'}
                      strokeWidth={isSelected ? 3 : 1}
                    />
                    <text
                      x={j * cellSize + cellSize / 2}
                      y={i * cellSize + cellSize / 2 - 6}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      className="text-sm font-semibold pointer-events-none fill-foreground"
                    >
                      {count}
                    </text>
                    <text
                      x={j * cellSize + cellSize / 2}
                      y={i * cellSize + cellSize / 2 + 12}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      className="text-xs pointer-events-none fill-foreground"
                    >
                      {pct.toFixed(1)}%
                    </text>
                  </g>
                )
              })
            )}
          </g>
        </svg>
      </div>

      <p className="mt-3 text-sm text-foreground">{confusionReading(data)}</p>

      {/* aria-live wrapper stays mounted so the panel's appearance is announced */}
      <div aria-live="polite">
      {selected !== null && (
        <div
          data-testid="confusion-cell-detail"
          className="mt-4 p-4 bg-primary/10 border border-primary/30 rounded-lg text-sm"
        >
          <h4 className="font-semibold text-foreground mb-2">Cell detail</h4>
          <dl className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div>
              <dt className="text-muted-foreground">Actual</dt>
              <dd className="font-medium text-foreground">{data.labels[selected.row]}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Predicted</dt>
              <dd className="font-medium text-foreground">{data.labels[selected.col]}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Count</dt>
              <dd className="font-medium text-foreground">{selectedCount}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">% of actual {data.labels[selected.row]}</dt>
              <dd className="font-medium text-foreground">
                {rowPercent(selected.row, selectedCount).toFixed(1)}%
              </dd>
            </div>
          </dl>
        </div>
      )}
      </div>
    </div>
  )
}
