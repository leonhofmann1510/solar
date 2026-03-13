import { defineStore } from 'pinia'
import { ref } from 'vue'
import { readingsApi } from '@/api/readings'
import type { InverterReading } from '@/types/reading'

export const useReadingsStore = defineStore('readings', () => {
  const inv1 = ref<InverterReading | null>(null)
  const inv2 = ref<InverterReading | null>(null)
  const history = ref<InverterReading[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchLatest() {
    try {
      const readings = await readingsApi.getLatest()
      for (const r of readings) {
        if (r.inverter_id === 'inv1') inv1.value = r
        if (r.inverter_id === 'inv2') inv2.value = r
      }
    } catch (e: any) {
      error.value = e.message
    }
  }

  async function fetchHistory(params: {
    inverter_id?: string
    from?: string
    to?: string
    limit?: number
  }) {
    loading.value = true
    error.value = null
    try {
      history.value = await readingsApi.getHistory(params)
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  function pushLiveReading(reading: InverterReading) {
    if (reading.inverter_id === 'inv1') inv1.value = reading
    if (reading.inverter_id === 'inv2') inv2.value = reading
  }

  return { inv1, inv2, history, loading, error, fetchLatest, fetchHistory, pushLiveReading }
})
