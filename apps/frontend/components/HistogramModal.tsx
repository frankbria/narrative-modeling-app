import React from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
)

interface HistogramModalProps {
  isOpen: boolean
  onClose: () => void
  columnName: string
  histogramData?: {
    bin_edges: number[]
    bin_counts: number[]
    bin_width: number
    min_value: number
    max_value: number
  }
}

export function HistogramModal({ isOpen, onClose, columnName, histogramData }: HistogramModalProps) {
  if (!isOpen || !histogramData) return null;

  // Prepare data for the chart
  const labels = histogramData.bin_edges.slice(0, -1).map((edge, index) => {
    const start = edge.toFixed(2)
    const end = histogramData.bin_edges[index + 1].toFixed(2)
    return `${start} - ${end}`
  })

  const data = {
    labels,
    datasets: [
      {
        label: 'Frequency',
        data: histogramData.bin_counts,
        backgroundColor: 'rgba(59, 130, 246, 0.7)', // Blue with higher opacity
        borderColor: 'rgba(37, 99, 235, 1)', // Darker blue border
        borderWidth: 1,
        borderRadius: 4, // Rounded corners for bars
      },
    ],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          font: {
            size: 14,
            weight: 'bold' as const,
          },
        },
      },
      title: {
        display: true,
        text: `Histogram for ${columnName}`,
        font: {
          size: 18,
          weight: 'bold' as const,
        },
        padding: {
          top: 10,
          bottom: 20,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Frequency',
          font: {
            size: 14,
            weight: 'bold' as const,
          },
        },
        grid: {
          color: 'rgba(0, 0, 0, 0.1)',
        },
      },
      x: {
        title: {
          display: true,
          text: 'Value Range',
          font: {
            size: 14,
            weight: 'bold' as const,
          },
        },
        grid: {
          color: 'rgba(0, 0, 0, 0.1)',
        },
      },
    },
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl bg-white">
        <DialogHeader className="border-b pb-4">
          <DialogTitle className="text-xl font-bold">Histogram for {columnName}</DialogTitle>
        </DialogHeader>
        <div className="p-4">
          <div className="h-[400px] bg-white p-4 rounded-lg shadow-sm">
            <Bar data={data} options={options} />
          </div>
          <div className="mt-4 p-3 bg-gray-50 rounded-md text-sm text-gray-700">
            <p className="font-medium">Summary Statistics:</p>
            <div className="grid grid-cols-3 gap-4 mt-2">
              <div>
                <p className="text-gray-500">Min</p>
                <p className="font-semibold">{histogramData.min_value.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-gray-500">Max</p>
                <p className="font-semibold">{histogramData.max_value.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-gray-500">Bin Width</p>
                <p className="font-semibold">{histogramData.bin_width.toFixed(2)}</p>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
} 