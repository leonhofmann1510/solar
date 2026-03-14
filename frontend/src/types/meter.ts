export interface MeterReading {
  id: number
  timestamp: string
  consumption_kwh: number  // E_in  — cumulative total consumed from grid
  feed_in_kwh: number      // E_out — cumulative total fed into grid
}

export interface MeterStatus {
  enabled: boolean
  ip: string
}

export interface MeterPoint {
  label: string
  consumption_kwh: number  // kWh delta in this period
  feed_in_kwh: number
}

export type MeterView = 'day' | 'week' | 'month' | 'year'
