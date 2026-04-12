import client from './client'

export interface AppSettings {
  timezone: string
  ev_wallbox_device_id: number | null
  ev_charging_capability_key: string
  ev_charging_value: string
  ev_charging_power_kw: number
  ev_battery_threshold_pct: number
  ev_efficiency_km_per_kwh: number
  ev_cost_per_100km_solar_eur: number
  ev_cost_per_100km_grid_eur: number
  ev_cost_per_100km_gas_eur: number
}

export async function getAppSettings(): Promise<AppSettings> {
  const { data } = await client.get<AppSettings>('/api/settings')
  return data
}

export async function patchAppSettings(patch: Partial<AppSettings>): Promise<AppSettings> {
  const { data } = await client.patch<AppSettings>('/api/settings', patch)
  return data
}
