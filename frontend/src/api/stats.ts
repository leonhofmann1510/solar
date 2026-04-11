import client from './client'
import type { SelfSufficiencyOut, StatChartPoint, StatsView } from '@/types/stats'

export async function getStatsChart(view: StatsView): Promise<StatChartPoint[]> {
  const { data } = await client.get<StatChartPoint[]>('/api/stats/chart', {
    params: { view },
  })
  return data
}

export async function getSelfSufficiency(): Promise<SelfSufficiencyOut> {
  const { data } = await client.get<SelfSufficiencyOut>('/api/stats/self-sufficiency')
  return data
}
