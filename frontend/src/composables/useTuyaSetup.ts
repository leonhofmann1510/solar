import { ref, onUnmounted } from 'vue'
import { devicesApi } from '@/api/devices'
import { useDevicesStore } from '@/stores/devices'

type TuyaSetupStatus = 'idle' | 'pending' | 'success' | 'failed'

const POLL_INTERVAL_MS = 2000
const TIMEOUT_MS = 5 * 60 * 1000

export function useTuyaSetup() {
  const qrUrl = ref<string | null>(null)
  const status = ref<TuyaSetupStatus>('idle')
  const devicesFound = ref(0)
  const errorMessage = ref<string | null>(null)

  let sessionId: string | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let timeoutTimer: ReturnType<typeof setTimeout> | null = null

  async function startSetup(userCode: string) {
    reset()
    status.value = 'pending'
    errorMessage.value = null

    try {
      const res = await devicesApi.startTuyaLogin(userCode)
      sessionId = res.session_id
      qrUrl.value = res.qr_url
      pollTimer = setInterval(pollStatus, POLL_INTERVAL_MS)
      timeoutTimer = setTimeout(() => {
        if (status.value === 'pending') {
          status.value = 'failed'
          errorMessage.value = 'Login timed out. Please try again.'
          stopPolling()
        }
      }, TIMEOUT_MS)
    } catch (e: any) {
      status.value = 'failed'
      errorMessage.value = e.response?.data?.detail || e.message || 'Failed to start Tuya setup'
    }
  }

  async function pollStatus() {
    if (!sessionId || status.value !== 'pending') return

    try {
      const res = await devicesApi.getTuyaLoginStatus(sessionId)
      if (res.status === 'success') {
        status.value = 'success'
        devicesFound.value = res.devices_found
        stopPolling()
        // Refresh the devices store so the new pending devices are immediately visible
        const devicesStore = useDevicesStore()
        await Promise.all([devicesStore.fetchPending(), devicesStore.fetchAll()])
      } else if (res.status === 'failed') {
        status.value = 'failed'
        errorMessage.value = 'Login failed. Please try again.'
        stopPolling()
      }
    } catch {
      // Network error during poll — keep polling, don't fail yet
    }
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    if (timeoutTimer) {
      clearTimeout(timeoutTimer)
      timeoutTimer = null
    }
  }

  function reset() {
    stopPolling()
    qrUrl.value = null
    status.value = 'idle'
    devicesFound.value = 0
    errorMessage.value = null
    sessionId = null
  }

  onUnmounted(stopPolling)

  return { qrUrl, status, devicesFound, errorMessage, startSetup, reset }
}
