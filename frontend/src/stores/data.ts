import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  deleteEVSession,
  deleteInverterStat,
  deleteMeterReading,
  getDataCounts,
  getEVSessionRecords,
  getInverterStats,
  getMeterReadingRecords,
  patchEVSession,
  patchInverterStat,
  patchMeterReading,
} from '@/api/data'
import type {
  DataCounts,
  EVSessionRecord,
  EVSessionUpdate,
  InverterDailyStat,
  InverterDailyStatUpdate,
  MeterReadingRecord,
  MeterReadingUpdate,
} from '@/types/data'

export const useDataStore = defineStore('data', () => {
  const inverterStats = ref<InverterDailyStat[]>([])
  const meterReadings = ref<MeterReadingRecord[]>([])
  const evSessions = ref<EVSessionRecord[]>([])
  const counts = ref<DataCounts>({ inverter_stats: 0, meter_readings: 0, ev_sessions: 0 })

  const filter = ref<{ dateFrom: Date | null; dateTo: Date | null }>({
    dateFrom: null,
    dateTo: null,
  })

  const loadingInverter = ref(false)
  const loadingMeter = ref(false)
  const loadingEV = ref(false)

  const meterLoaded = ref(false)
  const evLoaded = ref(false)

  function filterParams() {
    return { date_from: filter.value.dateFrom, date_to: filter.value.dateTo }
  }

  async function fetchInverterStats(page = 0, rows = 100) {
    loadingInverter.value = true
    try {
      inverterStats.value = await getInverterStats({
        ...filterParams(),
        limit: rows,
        offset: page * rows,
      })
    } finally {
      loadingInverter.value = false
    }
  }

  async function fetchMeterReadings(page = 0, rows = 100) {
    loadingMeter.value = true
    try {
      meterReadings.value = await getMeterReadingRecords({
        ...filterParams(),
        limit: rows,
        offset: page * rows,
      })
      meterLoaded.value = true
    } finally {
      loadingMeter.value = false
    }
  }

  async function fetchEVSessions(page = 0, rows = 100) {
    loadingEV.value = true
    try {
      evSessions.value = await getEVSessionRecords({
        ...filterParams(),
        limit: rows,
        offset: page * rows,
      })
      evLoaded.value = true
    } finally {
      loadingEV.value = false
    }
  }

  async function fetchCounts() {
    counts.value = await getDataCounts(filterParams())
  }

  async function updateInverterStat(id: number, body: InverterDailyStatUpdate) {
    const updated = await patchInverterStat(id, body)
    const idx = inverterStats.value.findIndex((r) => r.id === id)
    if (idx !== -1) inverterStats.value[idx] = updated
  }

  async function deleteInverterStatRecord(id: number) {
    await deleteInverterStat(id)
    inverterStats.value = inverterStats.value.filter((r) => r.id !== id)
    counts.value.inverter_stats = Math.max(0, counts.value.inverter_stats - 1)
  }

  async function updateMeterReading(id: number, body: MeterReadingUpdate) {
    const updated = await patchMeterReading(id, body)
    const idx = meterReadings.value.findIndex((r) => r.id === id)
    if (idx !== -1) meterReadings.value[idx] = updated
  }

  async function deleteMeterReadingRecord(id: number) {
    await deleteMeterReading(id)
    meterReadings.value = meterReadings.value.filter((r) => r.id !== id)
    counts.value.meter_readings = Math.max(0, counts.value.meter_readings - 1)
  }

  async function updateEVSession(id: number, body: EVSessionUpdate) {
    const updated = await patchEVSession(id, body)
    const idx = evSessions.value.findIndex((r) => r.id === id)
    if (idx !== -1) evSessions.value[idx] = updated
  }

  async function deleteEVSessionRecord(id: number) {
    await deleteEVSession(id)
    evSessions.value = evSessions.value.filter((r) => r.id !== id)
    counts.value.ev_sessions = Math.max(0, counts.value.ev_sessions - 1)
  }

  return {
    inverterStats,
    meterReadings,
    evSessions,
    counts,
    filter,
    loadingInverter,
    loadingMeter,
    loadingEV,
    meterLoaded,
    evLoaded,
    fetchInverterStats,
    fetchMeterReadings,
    fetchEVSessions,
    fetchCounts,
    updateInverterStat,
    deleteInverterStatRecord,
    updateMeterReading,
    deleteMeterReadingRecord,
    updateEVSession,
    deleteEVSessionRecord,
  }
})
