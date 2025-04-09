import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export interface StatItem {
  field: string
  type: 'numeric' | 'date' | 'text'
  count: number
  missing: number
  unique: number
  min?: number | string | null
  max?: number | string | null
  mean?: number | null
  median?: number | null
  mode?: number[] | null
  std?: number | null
  minLength?: number
  maxLength?: number
  avgLength?: number
}

// Function to calculate descriptive statistics for a dataset
export function calculateDescriptiveStats(data: (string | number | boolean | null)[][], headers: string[]): StatItem[] {
  if (!data || data.length === 0 || !headers || headers.length === 0) {
    return []
  }

  // Initialize result array
  const stats = headers.map((header, index) => {
    // Extract column data
    const columnData = data.map(row => row[index])
    
    // Determine data type
    const isNumeric = columnData.every(val => 
      typeof val === 'number' || 
      (typeof val === 'string' && !isNaN(Number(val)) && val.trim() !== '')
    )
    
    const isDate = columnData.every(val => 
      typeof val === 'string' && 
      !isNaN(Date.parse(val)) && 
      val.trim() !== ''
    )
    
    // Calculate statistics based on data type
    if (isNumeric) {
      const numericData = columnData
        .map(val => typeof val === 'string' ? Number(val) : val)
        .filter((val): val is number => typeof val === 'number' && !isNaN(val))
      
      if (numericData.length === 0) {
        return {
          field: header,
          type: 'numeric' as const,
          count: columnData.length,
          missing: columnData.filter(val => val === null || val === undefined || val === '').length,
          unique: new Set(columnData).size,
          min: null,
          max: null,
          mean: null,
          median: null,
          mode: null,
          std: null
        }
      }
      
      // Sort for median calculation
      const sorted = [...numericData].sort((a, b) => a - b)
      
      // Calculate mean
      const sum = numericData.reduce((acc, val) => acc + val, 0)
      const mean = sum / numericData.length
      
      // Calculate median
      const median = sorted.length % 2 === 0
        ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
        : sorted[Math.floor(sorted.length / 2)]
      
      // Calculate mode
      const frequency: Record<number, number> = {}
      numericData.forEach(val => {
        frequency[val] = (frequency[val] || 0) + 1
      })
      const maxFreq = Math.max(...Object.values(frequency))
      const mode = Object.keys(frequency)
        .filter(key => frequency[Number(key)] === maxFreq)
        .map(Number)
      
      // Calculate standard deviation
      const variance = numericData.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / numericData.length
      const std = Math.sqrt(variance)
      
      return {
        field: header,
        type: 'numeric' as const,
        count: columnData.length,
        missing: columnData.filter(val => val === null || val === undefined || val === '').length,
        unique: new Set(columnData).size,
        min: Math.min(...numericData),
        max: Math.max(...numericData),
        mean,
        median,
        mode,
        std
      }
    } else if (isDate) {
      const dateData = columnData
        .filter((val): val is string => typeof val === 'string')
        .map(val => new Date(val))
      
      return {
        field: header,
        type: 'date' as const,
        count: columnData.length,
        missing: columnData.filter(val => val === null || val === undefined || val === '').length,
        unique: new Set(columnData).size,
        min: new Date(Math.min(...dateData.map(d => d.getTime()))).toISOString().split('T')[0],
        max: new Date(Math.max(...dateData.map(d => d.getTime()))).toISOString().split('T')[0]
      }
    } else {
      // Text data
      const textData = columnData
        .filter((val): val is string | number | boolean => 
          val !== null && val !== undefined && val !== '')
        .map(val => String(val))
      
      return {
        field: header,
        type: 'text' as const,
        count: columnData.length,
        missing: columnData.filter(val => val === null || val === undefined || val === '').length,
        unique: new Set(columnData).size,
        minLength: textData.length > 0 ? Math.min(...textData.map(val => val.length)) : 0,
        maxLength: textData.length > 0 ? Math.max(...textData.map(val => val.length)) : 0,
        avgLength: textData.length > 0 
          ? textData.reduce((acc, val) => acc + val.length, 0) / textData.length 
          : 0
      }
    }
  })
  
  return stats
} 