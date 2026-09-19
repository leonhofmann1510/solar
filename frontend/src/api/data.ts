import client from './client'
import type {
  DataCounts,
  EVSessionCreate,
  EVSessionRecord,
  EVSessionUpdate,
  InverterDailyStat,
  InverterDailyStatCreate,
  InverterDailyStatUpdate,
  MeterReadingCreate,
  MeterReadingRecord,
  MeterReadingUpdate,
} from '@/types/data'

function isoOrNull(d: Date | null | undefined): string | undefined {
  return d ? d.toISOString().split('T')[0] : undefined
}

// ── Inverter Stats ─────────────────────────────────────────────────────────────

export async function getInverterStats(params: {
  date_from?: Date | null
  date_to?: Date | null
  inverter_id?: string
  limit?: number
  offset?: number
}): Promise<InverterDailyStat[]> {
  const { data } = await client.get<InverterDailyStat[]>('/api/data/inverter-stats', {
    params: {
      date_from: isoOrNull(params.date_from),
      date_to: isoOrNull(params.date_to),
      inverter_id: params.inverter_id,
      limit: params.limit ?? 100,
      offset: params.offset ?? 0,
    },
  })
  return data
}

export async function patchInverterStat(id: number, body: InverterDailyStatUpdate): Promise<InverterDailyStat> {
  const { data } = await client.patch<InverterDailyStat>(`/api/data/inverter-stats/${id}`, body)
  return data
}

export async function deleteInverterStat(id: number): Promise<void> {
  await client.delete(`/api/data/inverter-stats/${id}`)
}

export async function createInverterStat(body: InverterDailyStatCreate): Promise<InverterDailyStat> {
  const { data } = await client.post<InverterDailyStat>('/api/data/inverter-stats', body)
  return data
}

// ── Meter Readings ─────────────────────────────────────────────────────────────

export async function getMeterReadingRecords(params: {
  date_from?: Date | null
  date_to?: Date | null
  limit?: number
  offset?: number
}): Promise<MeterReadingRecord[]> {
  const { data } = await client.get<MeterReadingRecord[]>('/api/data/meter-readings', {
    params: {
      date_from: isoOrNull(params.date_from),
      date_to: isoOrNull(params.date_to),
      limit: params.limit ?? 100,
      offset: params.offset ?? 0,
    },
  })
  return data
}

export async function patchMeterReading(id: number, body: MeterReadingUpdate): Promise<MeterReadingRecord> {
  const { data } = await client.patch<MeterReadingRecord>(`/api/data/meter-readings/${id}`, body)
  return data
}

export async function deleteMeterReading(id: number): Promise<void> {
  await client.delete(`/api/data/meter-readings/${id}`)
}

export async function createMeterReading(body: MeterReadingCreate): Promise<MeterReadingRecord> {
  const { data } = await client.post<MeterReadingRecord>('/api/data/meter-readings', body)
  return data
}

// ── EV Sessions ────────────────────────────────────────────────────────────────

export async function getEVSessionRecords(params: {
  date_from?: Date | null
  date_to?: Date | null
  limit?: number
  offset?: number
}): Promise<EVSessionRecord[]> {
  const { data } = await client.get<EVSessionRecord[]>('/api/data/ev-sessions', {
    params: {
      date_from: isoOrNull(params.date_from),
      date_to: isoOrNull(params.date_to),
      limit: params.limit ?? 100,
      offset: params.offset ?? 0,
    },
  })
  return data
}

export async function patchEVSession(id: number, body: EVSessionUpdate): Promise<EVSessionRecord> {
  const { data } = await client.patch<EVSessionRecord>(`/api/data/ev-sessions/${id}`, body)
  return data
}

export async function deleteEVSession(id: number): Promise<void> {
  await client.delete(`/api/data/ev-sessions/${id}`)
}

export async function createEVSession(body: EVSessionCreate): Promise<EVSessionRecord> {
  const { data } = await client.post<EVSessionRecord>('/api/data/ev-sessions', body)
  return data
}

// ── Counts ─────────────────────────────────────────────────────────────────────

export async function getDataCounts(params: {
  date_from?: Date | null
  date_to?: Date | null
}): Promise<DataCounts> {
  const { data } = await client.get<DataCounts>('/api/data/counts', {
    params: {
      date_from: isoOrNull(params.date_from),
      date_to: isoOrNull(params.date_to),
    },
  })
  return data
}
