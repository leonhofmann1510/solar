export interface StatChartPoint {
  label: string
  yield_kwh: number
  feed_in_kwh: number
  grid_buy_kwh: number
  self_consumption_kwh: number
}

export type StatsView = 'day' | 'week' | 'month' | 'year'
