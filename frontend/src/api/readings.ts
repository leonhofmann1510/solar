import client from './client'
import type { InverterReading } from '@/types/reading'

export const readingsApi = {
  getLatest(): Promise<InverterReading[]> {
    return client.get('/api/readings/latest').then((r) => r.data)
  },

  getHistory(params: {
    inverter_id?: string
    from?: string
    to?: string
    limit?: number
  }): Promise<InverterReading[]> {
    return client.get('/api/readings', { params }).then((r) => r.data)
  },

  getHealth(): Promise<{ status: string; inverters: { id: string; last_seen: string | null; connected: boolean }[] }> {
    return client.get('/api/health').then((r) => r.data)
  },
}
