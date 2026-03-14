<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { useReadingsStore } from '@/stores/readings'
import { useDevicesStore } from '@/stores/devices'

const readingsStore = useReadingsStore()
const devicesStore = useDevicesStore()

let socket: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null

function connect() {
  const url = `${import.meta.env.VITE_WS_BASE_URL}/ws`
  socket = new WebSocket(url)

  socket.onopen = () => {
    console.log('[WS] Connected')
  }

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)

      if (data.event === 'device_state_changed') {
        devicesStore.updateDeviceState(data.device_id, data.capability_key, data.value)
      } else if (data.event === 'device_discovered') {
        devicesStore.fetchPending()
      } else if (data.inverter_id) {
        readingsStore.pushLiveReading(data)
      }
    } catch {
      console.warn('[WS] Could not parse message', event.data)
    }
  }

  socket.onclose = () => {
    console.log('[WS] Disconnected — reconnecting in 5s')
    reconnectTimer = setTimeout(connect, 5_000)
  }

  socket.onerror = (err) => {
    console.error('[WS] Error', err)
    socket?.close()
  }
}

connect()

onUnmounted(() => {
  if (reconnectTimer) clearTimeout(reconnectTimer)
  socket?.close()
})
</script>

<template>
  <router-view />
</template>
