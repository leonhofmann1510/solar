import client from './client'
import type { MeterPoint, MeterReading, MeterStatus, MeterView } from '@/types/meter'

export async function getMeterStatus(): Promise<MeterStatus> {
  const { data } = await client.get<MeterStatus>('/api/meter/status')
  return data
}

export async function getMeterLatest(): Promise<MeterReading | null> {
  const { data } = await client.get<MeterReading | null>('/api/meter/latest')
  return data
}

export async function getMeterReadings(view: MeterView): Promise<MeterPoint[]> {
  const { data } = await client.get<MeterPoint[]>('/api/meter/readings', {
    params: { view },
  })
  return data
}
