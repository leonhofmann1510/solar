import { ref, onUnmounted } from 'vue'
import type { InverterReading } from '@/types/reading'

export function useWebSocket() {
  const latestReading = ref<InverterReading | null>(null)
  const connected = ref(false)

  let socket: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function connect() {
    const url = `${import.meta.env.VITE_WS_BASE_URL}/ws`
    socket = new WebSocket(url)

    socket.onopen = () => {
      connected.value = true
      console.log('[WS] Connected')
    }

    socket.onmessage = (event) => {
      try {
        latestReading.value = JSON.parse(event.data)
      } catch {
        console.warn('[WS] Could not parse message', event.data)
      }
    }

    socket.onclose = () => {
      connected.value = false
      console.log('[WS] Disconnected — reconnecting in 5s')
      reconnectTimer = setTimeout(connect, 5_000)
    }

    socket.onerror = (err) => {
      console.error('[WS] Error', err)
      socket?.close()
    }
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    socket?.close()
  }

  connect()

  onUnmounted(disconnect)

  return { latestReading, connected }
}
