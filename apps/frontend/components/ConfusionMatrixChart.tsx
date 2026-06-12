'use client'

import React, { useEffect, useMemo, useRef, useState } from 'react'
import type { ConfusionMatrixData } from '@/lib/types/evaluation'

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
 * ResizeObserver, HSL color scale with intensity normalized by the actual-class
 * (row) total. Correct predictions (diagonal) use a blue scale, errors a red
 * scale. Cells are keyboard-focusable; clicking (or pressing Enter/Space)
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
      <div className="flex items-center justify-center h-64 bg-gray-50 rounded-lg border border-gray-200">
        <p className="text-gray-500">No confusion matrix data available</p>
      </div>
    )
  }

  const rowPercent = (row: number, count: number): number =>
    rowTotals[row] > 0 ? (count / rowTotals[row]) * 100 : 0

  const getColor = (row: number, col: number, count: number) => {
    const intensity = rowTotals[row] > 0 ? count / rowTotals[row] : 0
    // Blue scale for correct predictions (diagonal), red scale for errors.
    const hue = row === col ? 217 : 0
    return `hsl(${hue}, 80%, ${95 - intensity * 45}%)`
  }

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
    <div className="w-full">
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
              className="text-xs font-semibold fill-gray-700"
            >
              Predicted
            </text>
            <text
              transform={`translate(${-labelWidth + 12}, ${(numLabels * cellSize) / 2}) rotate(-90)`}
              textAnchor="middle"
              className="text-xs font-semibold fill-gray-700"
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
                className="text-xs font-medium fill-gray-700"
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
                className="text-xs font-medium fill-gray-700"
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
                      fill={getColor(i, j, count)}
                      stroke={isSelected ? '#1d4ed8' : 'white'}
                      strokeWidth={isSelected ? 3 : 1}
                    />
                    <text
                      x={j * cellSize + cellSize / 2}
                      y={i * cellSize + cellSize / 2 - 6}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      className="text-sm font-semibold pointer-events-none"
                      style={{
                        fill: pct > 60 ? '#1f2937' : '#374151',
                      }}
                    >
                      {count}
                    </text>
                    <text
                      x={j * cellSize + cellSize / 2}
                      y={i * cellSize + cellSize / 2 + 12}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      className="text-xs pointer-events-none fill-gray-600"
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

      {/* aria-live wrapper stays mounted so the panel's appearance is announced */}
      <div aria-live="polite">
      {selected !== null && (
        <div
          data-testid="confusion-cell-detail"
          className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm"
        >
          <h4 className="font-semibold text-gray-900 mb-2">Cell detail</h4>
          <dl className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div>
              <dt className="text-gray-600">Actual</dt>
              <dd className="font-medium text-gray-900">{data.labels[selected.row]}</dd>
            </div>
            <div>
              <dt className="text-gray-600">Predicted</dt>
              <dd className="font-medium text-gray-900">{data.labels[selected.col]}</dd>
            </div>
            <div>
              <dt className="text-gray-600">Count</dt>
              <dd className="font-medium text-gray-900">{selectedCount}</dd>
            </div>
            <div>
              <dt className="text-gray-600">% of actual {data.labels[selected.row]}</dt>
              <dd className="font-medium text-gray-900">
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
