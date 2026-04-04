import client from './client'

export interface AppSettings {
  timezone: string
}

export async function getAppSettings(): Promise<AppSettings> {
  const { data } = await client.get<AppSettings>('/api/settings')
  return data
}

export async function patchAppSettings(patch: Partial<AppSettings>): Promise<AppSettings> {
  const { data } = await client.patch<AppSettings>('/api/settings', patch)
  return data
}
