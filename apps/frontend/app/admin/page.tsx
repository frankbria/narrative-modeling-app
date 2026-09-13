'use client'

import { HealthMonitor } from '@/components/HealthMonitor'

/**
 * Admin dashboard.
 *
 * Only measured values belong here (#478): the old page hardcoded a "Security
 * Overview" of tiles reading "Active"/"Enabled"/"SHA-256" that measured nothing,
 * and an internal "Sprint 1 Achievement Summary" retrospective — both presented
 * to customers as a status report. Asserting an unverified security posture to a
 * customer is a false statement about their data, so the honest fix is to remove
 * them (issue AC3). What remains is the one live widget, HealthMonitor, which
 * reads real backend health (its own polling targets are #479).
 */
export default function AdminPage() {
  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Admin Dashboard</h1>
        <p className="text-muted-foreground">Monitor system health</p>
      </div>

      <HealthMonitor refreshInterval={10000} />
    </div>
  )
}
