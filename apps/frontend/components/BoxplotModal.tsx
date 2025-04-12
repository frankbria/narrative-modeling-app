import React from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'

// Import the boxplot plugin
import 'chartjs-chart-box-and-violin-plot'

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
)

interface BoxplotModalProps {
  isOpen: boolean
  onClose: () => void
  columnName: string
  boxplotData: {
    min: number
    q1: number
    median: number
    q3: number
    max: number
    outliers: number[]
  }
}

export function BoxplotModal({ isOpen, onClose, columnName, boxplotData }: BoxplotModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl bg-white">
        <DialogHeader className="border-b pb-4">
          <DialogTitle className="text-xl font-bold">Boxplot for {columnName}</DialogTitle>
        </DialogHeader>
        <div className="p-4">
          <div className="h-[400px] bg-white p-4 rounded-lg shadow-sm">
            {/* Display a simple boxplot visualization using divs */}
            <div className="flex flex-col items-center justify-center h-full">
              <div className="w-full max-w-md">
                <div className="relative h-8 bg-blue-100 rounded-t-md">
                  {/* Median line */}
                  <div 
                    className="absolute h-8 w-1 bg-blue-600 left-1/2 transform -translate-x-1/2"
                    style={{ top: 0 }}
                  ></div>
                </div>
                <div className="h-2 bg-blue-200"></div>
                <div className="h-2 bg-blue-300"></div>
                <div className="h-2 bg-blue-400"></div>
                <div className="h-2 bg-blue-500"></div>
                <div className="h-2 bg-blue-600"></div>
                <div className="h-2 bg-blue-700"></div>
                <div className="h-2 bg-blue-800"></div>
                <div className="h-2 bg-blue-900"></div>
                <div className="h-2 bg-blue-950"></div>
                <div className="h-2 bg-gray-900"></div>
                <div className="h-2 bg-gray-800"></div>
                <div className="h-2 bg-gray-700"></div>
                <div className="h-2 bg-gray-600"></div>
                <div className="h-2 bg-gray-500"></div>
                <div className="h-2 bg-gray-400"></div>
                <div className="h-2 bg-gray-300"></div>
                <div className="h-2 bg-gray-200"></div>
                <div className="h-2 bg-gray-100 rounded-b-md"></div>
              </div>
              <div className="mt-4 text-center">
                <p className="text-sm text-gray-500">Min: {boxplotData.min.toFixed(2)}</p>
                <p className="text-sm text-gray-500">Q1: {boxplotData.q1.toFixed(2)}</p>
                <p className="text-sm font-bold">Median: {boxplotData.median.toFixed(2)}</p>
                <p className="text-sm text-gray-500">Q3: {boxplotData.q3.toFixed(2)}</p>
                <p className="text-sm text-gray-500">Max: {boxplotData.max.toFixed(2)}</p>
              </div>
            </div>
          </div>
          <div className="mt-4 p-3 bg-gray-50 rounded-md text-sm text-gray-700">
            <p className="font-medium">Summary Statistics:</p>
            <div className="grid grid-cols-3 gap-4 mt-2">
              <div>
                <p className="text-gray-500">Min</p>
                <p className="font-semibold">{boxplotData.min.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-gray-500">Q1</p>
                <p className="font-semibold">{boxplotData.q1.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-gray-500">Median</p>
                <p className="font-semibold">{boxplotData.median.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-gray-500">Q3</p>
                <p className="font-semibold">{boxplotData.q3.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-gray-500">Max</p>
                <p className="font-semibold">{boxplotData.max.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-gray-500">Outliers</p>
                <p className="font-semibold">{boxplotData.outliers.length}</p>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
} 