export interface EVSession {
  id: number
  started_at: string
  ended_at: string | null
  kwh_total: number
  kwh_solar: number
  kwh_grid: number
  duration_solar_seconds: number
  duration_grid_seconds: number
  charging_power_kw: number
  efficiency_km_per_kwh: number
  cost_per_100km_solar_eur: number
  cost_per_100km_grid_eur: number
  cost_per_100km_gas_eur: number
  cost_eur: number
  savings_vs_gas_eur: number
}

export interface EVStatus {
  enabled: boolean
  configured: boolean
  active_session: EVSession | null
}

export interface EVSummary {
  this_week_kwh: number
  last_week_kwh: number
  this_week_km: number
  last_week_km: number
  total_savings_eur: number
  total_sessions: number
}
