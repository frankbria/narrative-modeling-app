'use client'

import React from 'react'
import { Badge } from '@/components/ui/badge'
import { AlertCircle, AlertTriangle, Info, XCircle } from 'lucide-react'

interface IssueSeverityBadgeProps {
  severity: 'critical' | 'high' | 'medium' | 'low' | string
  showIcon?: boolean
  className?: string
}

export function IssueSeverityBadge({
  severity,
  showIcon = true,
  className = ''
}: IssueSeverityBadgeProps) {
  const getVariant = (): 'destructive' | 'secondary' | 'outline' | 'default' => {
    switch (severity) {
      case 'critical':
      case 'high':
        return 'destructive'
      case 'medium':
        return 'secondary'
      case 'low':
        return 'outline'
      default:
        return 'default'
    }
  }

  const getIcon = () => {
    switch (severity) {
      case 'critical':
        return <XCircle className="h-3 w-3" />
      case 'high':
        return <AlertCircle className="h-3 w-3" />
      case 'medium':
        return <AlertTriangle className="h-3 w-3" />
      case 'low':
        return <Info className="h-3 w-3" />
      default:
        return null
    }
  }

  const getLabel = () => {
    return severity.charAt(0).toUpperCase() + severity.slice(1)
  }

  return (
    <Badge variant={getVariant()} className={`gap-1 ${className}`}>
      {showIcon && getIcon()}
      {getLabel()}
    </Badge>
  )
}
