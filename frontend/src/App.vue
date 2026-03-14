<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { useReadingsStore } from '@/stores/readings'
import { useDevicesStore } from '@/stores/devices'
import { useMeterStore } from '@/stores/meter'
import Toast from 'primevue/toast'

const readingsStore = useReadingsStore()
const devicesStore = useDevicesStore()
const meterStore = useMeterStore()

const wsConnected = ref(false)
let socket: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null

function connect() {
  const url = `${import.meta.env.VITE_WS_BASE_URL}/ws`
  socket = new WebSocket(url)

  socket.onopen = () => {
    wsConnected.value = true
  }

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)

      if (data.event === 'device_state_changed') {
        devicesStore.updateDeviceState(data.device_id, data.capability_key, data.value)
      } else if (data.event === 'device_discovered') {
        devicesStore.fetchPending()
      } else if (data.event === 'meter_reading') {
        meterStore.pushLiveReading(data)
      } else if (data.inverter_id) {
        readingsStore.pushLiveReading(data)
      }
    } catch {
      console.warn('[WS] Could not parse message', event.data)
    }
  }

  socket.onclose = () => {
    wsConnected.value = false
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
  <!-- WS disconnect banner -->
  <div
    v-if="!wsConnected"
    class="fixed top-0 left-0 right-0 z-50 bg-sf-amber-500 text-white text-center text-sm py-1.5 font-medium"
  >
    Live data disconnected — reconnecting...
  </div>

  <Toast position="top-right" />

  <router-view />
</template>
