import client from './client'
import type { StatChartPoint, StatsView } from '@/types/stats'

export async function getStatsChart(view: StatsView): Promise<StatChartPoint[]> {
  const { data } = await client.get<StatChartPoint[]>('/api/stats/chart', {
    params: { view },
  })
  return data
}
