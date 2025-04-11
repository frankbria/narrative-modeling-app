import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export interface StatItem {
  field_name: string
  field_type: string
  count: number
  missing_values: number
  unique_values: number
  numeric_stats?: {
    min: number
    max: number
    mean: number
    median: number
    mode: number
    std_dev: number
    histogram?: {
      bins: number[]
      counts: number[]
    }
  }
  categorical_stats?: {
    top_values: Array<{
      value: string
      count: number
    }>
  }
  date_stats?: {
    min_date: string
    max_date: string
  }
  text_stats?: {
    avg_length: number
    sample_values: string[]
  }
}

export function calculateDescriptiveStats(data: Array<Array<string | number | boolean | null>>, headers: string[]): StatItem[] {
  return headers.map((header, columnIndex) => {
    const columnData = data.map(row => row[columnIndex])
    const nonNullData = columnData.filter(value => value !== null && value !== undefined && value !== '')
    const numericData = nonNullData.map(value => typeof value === 'number' ? value : Number(value)).filter(value => !isNaN(value))
    
    const stats: StatItem = {
      field_name: header,
      field_type: numericData.length === nonNullData.length ? 'numeric' : 
                 nonNullData.every(value => !isNaN(Date.parse(String(value)))) ? 'date' :
                 typeof nonNullData[0] === 'string' && nonNullData[0].length > 50 ? 'text' : 'categorical',
      count: nonNullData.length,
      missing_values: data.length - nonNullData.length,
      unique_values: new Set(nonNullData).size,
    }

    if (stats.field_type === 'numeric' && numericData.length > 0) {
      const sorted = [...numericData].sort((a, b) => a - b)
      const sum = numericData.reduce((a, b) => a + b, 0)
      const mean = sum / numericData.length
      const median = sorted.length % 2 === 0 
        ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
        : sorted[Math.floor(sorted.length / 2)]
      
      // Calculate mode
      const valueCounts = new Map<number, number>()
      numericData.forEach(value => valueCounts.set(value, (valueCounts.get(value) || 0) + 1))
      const modeEntry = Array.from(valueCounts.entries()).reduce((a, b) => a[1] > b[1] ? a : b)
      const mode = modeEntry[0]
      
      // Calculate standard deviation
      const squareDiffs = numericData.map(value => Math.pow(value - mean, 2))
      const avgSquareDiff = squareDiffs.reduce((a, b) => a + b, 0) / numericData.length
      const stdDev = Math.sqrt(avgSquareDiff)

      // Create histogram data
      const binCount = Math.min(10, Math.ceil(Math.sqrt(numericData.length)))
      const binSize = (sorted[sorted.length - 1] - sorted[0]) / binCount
      const bins = Array.from({ length: binCount }, (_, i) => sorted[0] + i * binSize)
      const histogramCounts = new Array(binCount).fill(0)
      
      numericData.forEach(value => {
        const binIndex = Math.min(Math.floor((value - sorted[0]) / binSize), binCount - 1)
        histogramCounts[binIndex]++
      })

      stats.numeric_stats = {
        min: sorted[0],
        max: sorted[sorted.length - 1],
        mean,
        median,
        mode,
        std_dev: stdDev,
        histogram: {
          bins,
          counts: histogramCounts
        }
      }
    } else if (stats.field_type === 'categorical') {
      const valueCounts = new Map<string, number>()
      nonNullData.forEach(value => valueCounts.set(String(value), (valueCounts.get(String(value)) || 0) + 1))
      
      const topValues = Array.from(valueCounts.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([value, count]) => ({ value, count }))

      stats.categorical_stats = { top_values: topValues }
    } else if (stats.field_type === 'date') {
      const dates = nonNullData.map(value => new Date(String(value)))
      stats.date_stats = {
        min_date: new Date(Math.min(...dates.map(d => d.getTime()))).toISOString(),
        max_date: new Date(Math.max(...dates.map(d => d.getTime()))).toISOString()
      }
    } else if (stats.field_type === 'text') {
      const lengths = nonNullData.map(value => String(value).length)
      const avgLength = lengths.reduce((a, b) => a + b, 0) / lengths.length
      
      stats.text_stats = {
        avg_length: avgLength,
        sample_values: nonNullData.slice(0, 3).map(String)
      }
    }

    return stats
  })
}
