import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getMeterLatest, getMeterStatus } from '@/api/meter'
import type { MeterReading, MeterStatus } from '@/types/meter'

export const useMeterStore = defineStore('meter', () => {
  const status = ref<MeterStatus>({ enabled: false, ip: '' })
  const latest = ref<MeterReading | null>(null)

  async function fetchStatus() {
    status.value = await getMeterStatus()
  }

  async function fetchLatest() {
    latest.value = await getMeterLatest()
  }

  function pushLiveReading(data: { timestamp: string; consumption_kwh: number; feed_in_kwh: number }) {
    latest.value = { id: -1, ...data }
  }

  return { status, latest, fetchStatus, fetchLatest, pushLiveReading }
})
