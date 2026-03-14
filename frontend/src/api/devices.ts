import client from './client'
import type {
  Device,
  DeviceActionRequest,
  DeviceConfirm,
  DeviceUpdate,
} from '@/types/device'

export const devicesApi = {
  async getAll(): Promise<Device[]> {
    const { data } = await client.get<Device[]>('/api/devices')
    return data
  },

  async getPending(): Promise<Device[]> {
    const { data } = await client.get<Device[]>('/api/devices/pending')
    return data
  },

  async getOne(id: number): Promise<Device> {
    const { data } = await client.get<Device>(`/api/devices/${id}`)
    return data
  },

  async confirm(id: number, payload: DeviceConfirm): Promise<Device> {
    const { data } = await client.post<Device>(`/api/devices/${id}/confirm`, payload)
    return data
  },

  async update(id: number, payload: DeviceUpdate): Promise<Device> {
    const { data } = await client.put<Device>(`/api/devices/${id}`, payload)
    return data
  },

  async remove(id: number): Promise<void> {
    await client.delete(`/api/devices/${id}`)
  },

  async action(id: number, payload: DeviceActionRequest): Promise<{ ok: boolean }> {
    const { data } = await client.post<{ ok: boolean }>(`/api/devices/${id}/action`, payload)
    return data
  },

  async discoverTuya(): Promise<{ discovered: number }> {
    const { data } = await client.post<{ discovered: number }>('/api/devices/discover/tuya')
    return data
  },

  async discoverMdns(): Promise<{ discovered: number }> {
    const { data } = await client.post<{ discovered: number }>('/api/devices/discover/mdns')
    return data
  },

  async scanTuyaNetwork(): Promise<{ updated: number; scanned: number }> {
    const { data } = await client.post<{ updated: number; scanned: number }>('/api/devices/scan/tuya')
    return data
  },

  async readRawDps(id: number): Promise<{ device_id: number; raw_dps: Record<string, unknown> }> {
    const { data } = await client.post(`/api/devices/${id}/read`)
    return data
  },
}
