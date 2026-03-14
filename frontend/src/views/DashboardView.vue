<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useReadingsStore } from '@/stores/readings'
import { useDevicesStore } from '@/stores/devices'
import { useRulesStore } from '@/stores/rules'
import AppShell from '@/components/layout/AppShell.vue'
import SectionHeader from '@/components/shared/SectionHeader.vue'
import StatCard from '@/components/dashboard/StatCard.vue'
import BatteryCard from '@/components/dashboard/BatteryCard.vue'
import GridPowerCard from '@/components/dashboard/GridPowerCard.vue'
import SummaryLinkCard from '@/components/dashboard/SummaryLinkCard.vue'
import StatusDot from '@/components/shared/StatusDot.vue'
import Skeleton from 'primevue/skeleton'

const readingsStore = useReadingsStore()
const devicesStore = useDevicesStore()
const rulesStore = useRulesStore()

onMounted(async () => {
  await Promise.all([
    readingsStore.fetchLatest(),
    devicesStore.fetchAll(),
    devicesStore.fetchPending(),
    rulesStore.fetchAll(),
  ])
})

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
})

const dateStr = computed(() => {
  return new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  })
})

const loading = computed(() => !readingsStore.inv1 && !readingsStore.inv2)

const gridPowerW = computed(() => readingsStore.inv1?.grid_power_w ?? null)
const batterySoc = computed(() => readingsStore.inv1?.battery_soc_pct ?? null)
const batteryPower = computed(() => readingsStore.inv1?.battery_power_w ?? null)
const houseLoad = computed(() => readingsStore.inv1?.house_load_w ?? null)

const yieldToday = computed(() => readingsStore.inv1?.pv_yield_today_kwh ?? null)
const feedInToday = computed(() => readingsStore.inv1?.feed_in_today_kwh ?? null)
const gridBuyToday = computed(() => readingsStore.inv1?.grid_buy_today_kwh ?? null)
const selfConsumption = computed(() => {
  if (yieldToday.value == null || feedInToday.value == null) return null
  return Math.max(0, yieldToday.value - feedInToday.value)
})

const inv1Online = computed(() => readingsStore.inv1 != null)
const inv2Online = computed(() => readingsStore.inv2 != null)

const offlineDevices = computed(() =>
  devicesStore.devices.filter((d) => !d.enabled).length
)
const activeRules = computed(() =>
  rulesStore.rules.filter((r) => r.state === 'active').length
)
const idleRules = computed(() =>
  rulesStore.rules.filter((r) => r.state === 'idle').length
)
</script>

<template>
  <AppShell>
    <div class="mb-6">
      <h1 class="text-xl font-semibold text-sf-text-1">{{ greeting }}</h1>
      <p class="text-sm text-sf-text-2 mt-0.5">{{ dateStr }}</p>
    </div>

    <SectionHeader title="Solar System" />
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <StatCard
        label="PV Power"
        :value="readingsStore.inv1?.pv_power_w"
        unit="kW"
        icon="pi pi-sun"
        color="green"
        :loading="loading"
      />
      <GridPowerCard :gridPowerW="gridPowerW" :loading="loading" />
      <BatteryCard :soc="batterySoc" :power="batteryPower" :loading="loading" />
      <StatCard
        label="House Load"
        :value="houseLoad != null ? houseLoad : null"
        unit="W"
        icon="pi pi-home"
        color="neutral"
        :loading="loading"
      />
    </div>

    <SectionHeader title="Today" />
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <StatCard
        label="Yield"
        :value="yieldToday != null ? yieldToday.toFixed(1) : null"
        unit="kWh"
        icon="pi pi-chart-line"
        color="green"
        :loading="loading"
      />
      <StatCard
        label="Feed-in"
        :value="feedInToday != null ? feedInToday.toFixed(1) : null"
        unit="kWh"
        icon="pi pi-arrow-up"
        color="green"
        :loading="loading"
      />
      <StatCard
        label="Grid Buy"
        :value="gridBuyToday != null ? gridBuyToday.toFixed(1) : null"
        unit="kWh"
        icon="pi pi-arrow-down"
        color="amber"
        :loading="loading"
      />
      <StatCard
        label="Self-consumption"
        :value="selfConsumption != null ? selfConsumption.toFixed(1) : null"
        unit="kWh"
        icon="pi pi-replay"
        color="neutral"
        :loading="loading"
      />
    </div>

    <SectionHeader title="Inverters" />
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
      <div class="bg-sf-surface rounded-sf shadow-sf p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-medium text-sf-text-1">Inv 1 (Hybrid)</span>
          <StatusDot :color="inv1Online ? 'green' : 'red'" :label="inv1Online ? 'Online' : 'Offline'" />
        </div>
        <template v-if="readingsStore.inv1">
          <div class="flex items-center gap-4 text-xs text-sf-text-2">
            <span>Temp: {{ readingsStore.inv1.inverter_temp_c }}°C</span>
            <span>PV: {{ (readingsStore.inv1.pv_power_w / 1000).toFixed(1) }} kW</span>
          </div>
        </template>
        <Skeleton v-else height="1rem" width="60%" />
      </div>

      <div class="bg-sf-surface rounded-sf shadow-sf p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-medium text-sf-text-1">Inv 2 (String)</span>
          <StatusDot :color="inv2Online ? 'green' : 'red'" :label="inv2Online ? 'Online' : 'Offline'" />
        </div>
        <template v-if="readingsStore.inv2">
          <div class="flex items-center gap-4 text-xs text-sf-text-2">
            <span>Temp: {{ readingsStore.inv2.inverter_temp_c }}°C</span>
            <span>PV: {{ (readingsStore.inv2.pv_power_w / 1000).toFixed(1) }} kW</span>
          </div>
        </template>
        <Skeleton v-else height="1rem" width="60%" />
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <SummaryLinkCard
        icon="pi pi-objects-column"
        label="Devices"
        :total="devicesStore.devices.length"
        :alertCount="offlineDevices"
        alertLabel="offline"
        to="/devices"
      />
      <SummaryLinkCard
        icon="pi pi-bolt"
        label="Rules"
        :total="rulesStore.rules.length"
        :alertCount="activeRules"
        :alertLabel="`active, ${idleRules} idle`"
        to="/rules"
      />
    </div>
  </AppShell>
</template>
