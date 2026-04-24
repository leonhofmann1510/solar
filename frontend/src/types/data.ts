export interface InverterDailyStat {
  id: number
  timestamp: string
  inverter_id: string
  date: string
  hour: number
  pv_yield_today_kwh: number
  feed_in_today_kwh: number | null
  grid_buy_today_kwh: number | null
}

export interface InverterDailyStatUpdate {
  pv_yield_today_kwh?: number | null
  feed_in_today_kwh?: number | null
  grid_buy_today_kwh?: number | null
}

export interface MeterReadingRecord {
  id: number
  timestamp: string
  consumption_kwh: number
  feed_in_kwh: number
}

export interface MeterReadingUpdate {
  consumption_kwh?: number | null
  feed_in_kwh?: number | null
}

export interface EVSessionRecord {
  id: number
  started_at: string
  ended_at: string | null
  kwh_total: number
  kwh_solar: number
  kwh_grid: number
  charging_power_kw: number
  cost_eur: number
  savings_vs_gas_eur: number
}

export interface EVSessionUpdate {
  kwh_total?: number | null
  kwh_solar?: number | null
  kwh_grid?: number | null
  charging_power_kw?: number | null
  cost_eur?: number | null
  savings_vs_gas_eur?: number | null
}

export interface DataCounts {
  inverter_stats: number
  meter_readings: number
  ev_sessions: number
}
