import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getEVStatus, getEVSessions, getEVSummary } from '@/api/ev'
import type { EVSession, EVStatus, EVSummary } from '@/types/ev'

export const useEVStore = defineStore('ev', () => {
  const status = ref<EVStatus>({ enabled: false, configured: false, active_session: null })
  const sessions = ref<EVSession[]>([])
  const summary = ref<EVSummary | null>(null)

  const isCharging = computed(() => status.value.active_session !== null)

  async function fetchStatus() {
    status.value = await getEVStatus()
  }

  async function fetchSessions() {
    sessions.value = await getEVSessions()
  }

  async function fetchSummary() {
    summary.value = await getEVSummary()
  }

  function pushLiveStatus(data: {
    is_charging: boolean
    session_id: number | null
    duration_solar_seconds: number
    duration_grid_seconds: number
  }) {
    if (data.is_charging) {
      if (!status.value.active_session || status.value.active_session.id !== data.session_id) {
        // Session not in store yet (page loaded mid-session, or backend restarted) — fetch it
        fetchStatus()
      } else {
        status.value.active_session.duration_solar_seconds = data.duration_solar_seconds
        status.value.active_session.duration_grid_seconds = data.duration_grid_seconds
      }
    } else {
      status.value.active_session = null
    }
  }

  return { status, sessions, summary, isCharging, fetchStatus, fetchSessions, fetchSummary, pushLiveStatus }
})
