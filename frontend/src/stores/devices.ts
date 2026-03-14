import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { devicesApi } from '@/api/devices'
import type { Device, DeviceActionRequest, DeviceConfirm, DeviceUpdate } from '@/types/device'

export const useDevicesStore = defineStore('devices', () => {
  const devices = ref<Device[]>([])
  const pending = ref<Device[]>([])
  const loadingDevices = ref(false)
  const loadingPending = ref(false)
  const loading = computed(() => loadingDevices.value || loadingPending.value)
  const error = ref<string | null>(null)

  async function fetchAll() {
    loadingDevices.value = true
    try {
      devices.value = await devicesApi.getAll()
      error.value = null
    } catch (e: any) {
      error.value = e.message
    } finally {
      loadingDevices.value = false
    }
  }

  async function fetchPending() {
    loadingPending.value = true
    try {
      pending.value = await devicesApi.getPending()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loadingPending.value = false
    }
  }

  async function confirm(id: number, payload: DeviceConfirm) {
    const device = await devicesApi.confirm(id, payload)
    pending.value = pending.value.filter((d) => d.id !== id)
    devices.value.push(device)
    return device
  }

  async function update(id: number, payload: DeviceUpdate) {
    const updated = await devicesApi.update(id, payload)
    const idx = devices.value.findIndex((d) => d.id === id)
    if (idx !== -1) devices.value[idx] = updated
    return updated
  }

  async function remove(id: number) {
    await devicesApi.remove(id)
    devices.value = devices.value.filter((d) => d.id !== id)
    pending.value = pending.value.filter((d) => d.id !== id)
  }

  async function sendAction(id: number, payload: DeviceActionRequest) {
    return await devicesApi.action(id, payload)
  }

  async function discoverMdns() {
    const result = await devicesApi.discoverMdns()
    if (result.discovered > 0) await fetchPending()
    return result
  }

  async function scanTuyaNetwork() {
    const result = await devicesApi.scanTuyaNetwork()
    if (result.updated > 0) {
      await fetchAll()
      await fetchPending()
    }
    return result
  }

  function updateDeviceState(deviceId: number, capabilityKey: string, value: any) {
    const device = devices.value.find((d) => d.id === deviceId)
    if (!device) return

    const state = device.states.find((s) => s.capability_key === capabilityKey)
    if (state) {
      if (typeof value === 'boolean') state.value_boolean = value
      else if (typeof value === 'number') state.value_numeric = value
      else state.value_string = String(value)
      state.updated_at = new Date().toISOString()
    } else {
      device.states.push({
        capability_key: capabilityKey,
        value_boolean: typeof value === 'boolean' ? value : null,
        value_numeric: typeof value === 'number' ? value : null,
        value_string: typeof value === 'string' ? value : null,
        updated_at: new Date().toISOString(),
      })
    }
  }

  return {
    devices,
    pending,
    loading,
    error,
    fetchAll,
    fetchPending,
    confirm,
    update,
    remove,
    sendAction,
    discoverMdns,
    scanTuyaNetwork,
    updateDeviceState,
  }
})
