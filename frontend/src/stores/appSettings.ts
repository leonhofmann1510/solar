import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getAppSettings, patchAppSettings } from '@/api/app_settings'

export const useAppSettingsStore = defineStore('appSettings', () => {
  const timezone = ref('UTC')
  const loaded = ref(false)

  async function fetch() {
    const data = await getAppSettings()
    timezone.value = data.timezone
    loaded.value = true
  }

  async function setTimezone(tz: string) {
    const data = await patchAppSettings({ timezone: tz })
    timezone.value = data.timezone
  }

  return { timezone, loaded, fetch, setTimezone }
})
