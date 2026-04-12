import client from './client'
import type { EVSession, EVStatus, EVSummary } from '@/types/ev'

export async function getEVStatus(): Promise<EVStatus> {
  const { data } = await client.get<EVStatus>('/api/ev/status')
  return data
}

export async function getEVSessions(limit = 50, offset = 0): Promise<EVSession[]> {
  const { data } = await client.get<EVSession[]>('/api/ev/sessions', {
    params: { limit, offset },
  })
  return data
}

export async function getEVSummary(): Promise<EVSummary> {
  const { data } = await client.get<EVSummary>('/api/ev/summary')
  return data
}
