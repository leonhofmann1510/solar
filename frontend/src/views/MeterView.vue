<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  type TooltipItem,
} from 'chart.js'
import { Line } from 'vue-chartjs'
import Skeleton from 'primevue/skeleton'
import AppShell from '@/components/layout/AppShell.vue'
import SectionHeader from '@/components/shared/SectionHeader.vue'
import StatCard from '@/components/dashboard/StatCard.vue'
import { useMeterStore } from '@/stores/meter'
import { useAppSettingsStore } from '@/stores/appSettings'
import { getMeterReadings } from '@/api/meter'
import type { MeterPoint, MeterView } from '@/types/meter'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend)

const meterStore = useMeterStore()
const appSettingsStore = useAppSettingsStore()

const activeView = ref<MeterView>('day')
const chartPoints = ref<MeterPoint[]>([])
const loadingChart = ref(false)

const views: { key: MeterView; label: string }[] = [
  { key: 'day', label: 'Day' },
  { key: 'week', label: 'Week' },
  { key: 'month', label: 'Month' },
  { key: 'year', label: 'Year' },
]

async function loadChart() {
  loadingChart.value = true
  try {
    chartPoints.value = await getMeterReadings(activeView.value)
  } finally {
    loadingChart.value = false
  }
}

onMounted(async () => {
  await Promise.all([meterStore.fetchLatest(), loadChart()])
})

watch(activeView, loadChart)
watch(() => appSettingsStore.timezone, loadChart)

// ── Chart data ────────────────────────────────────────────────────────────────

const chartData = computed(() => ({
  labels: chartPoints.value.map((p) => p.label),
  datasets: [
    {
      label: 'Consumption',
      data: chartPoints.value.map((p) => p.consumption_kwh),
      borderColor: '#ef4444',
      backgroundColor: 'rgba(239,68,68,0.10)',
      fill: true,
      tension: 0.35,
      pointRadius: chartPoints.value.length > 48 ? 0 : 3,
    },
    {
      label: 'Feed-in',
      data: chartPoints.value.map((p) => p.feed_in_kwh),
      borderColor: '#22c55e',
      backgroundColor: 'rgba(34,197,94,0.10)',
      fill: true,
      tension: 0.35,
      pointRadius: chartPoints.value.length > 48 ? 0 : 3,
    },
  ],
}))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index' as const, intersect: false },
  plugins: {
    legend: {
      position: 'top' as const,
      labels: { color: '#64748b', font: { size: 12 }, boxWidth: 12, padding: 16 },
    },
    tooltip: {
      callbacks: {
        label: (ctx: TooltipItem<'line'>) =>
          ` ${ctx.dataset.label ?? ''}: ${(ctx.parsed as { y: number }).y.toFixed(3)} kWh`,
      },
    },
  },
  scales: {
    x: {
      grid: { color: 'rgba(100,116,139,0.08)' },
      ticks: { color: '#94a3b8', font: { size: 11 } },
    },
    y: {
      grid: { color: 'rgba(100,116,139,0.08)' },
      ticks: {
        color: '#94a3b8',
        font: { size: 11 },
        callback: (v: number | string) => `${Number(v).toFixed(2)} kWh`,
      },
    },
  },
}))

// ── Stat helpers ──────────────────────────────────────────────────────────────

const totalConsumption = computed(() =>
  meterStore.latest ? meterStore.latest.consumption_kwh.toFixed(1) : null,
)
const totalFeedIn = computed(() =>
  meterStore.latest ? meterStore.latest.feed_in_kwh.toFixed(1) : null,
)

const periodConsumption = computed(() => {
  if (!chartPoints.value.length) return null
  const sum = chartPoints.value.reduce((a, p) => a + p.consumption_kwh, 0)
  return sum.toFixed(2)
})
const periodFeedIn = computed(() => {
  if (!chartPoints.value.length) return null
  const sum = chartPoints.value.reduce((a, p) => a + p.feed_in_kwh, 0)
  return sum.toFixed(2)
})

const viewLabel = computed(() => views.find((v) => v.key === activeView.value)?.label ?? '')
const loading = computed(() => meterStore.latest === null)
</script>

<template>
  <AppShell>
    <div class="mb-6">
      <h1 class="text-xl font-semibold text-sf-text-1">Smart Meter</h1>
      <p class="text-sm text-sf-text-2 mt-0.5">Grid consumption &amp; feed-in</p>
    </div>

    <!-- Totals (cumulative from device) -->
    <SectionHeader title="All-time totals" />
    <div class="grid grid-cols-2 gap-3 mb-6">
      <StatCard
        label="Total consumed"
        :value="totalConsumption"
        unit="kWh"
        icon="pi pi-bolt"
        color="red"
        :loading="loading"
      />
      <StatCard
        label="Total fed in"
        :value="totalFeedIn"
        unit="kWh"
        icon="pi pi-arrow-up"
        color="green"
        :loading="loading"
      />
    </div>

    <!-- Period summary + chart -->
    <div class="flex items-center justify-between mb-3">
      <SectionHeader title="History" class="mb-0" />
      <div class="flex gap-1 bg-slate-100 rounded-sf p-1">
        <button
          v-for="v in views"
          :key="v.key"
          @click="activeView = v.key"
          class="px-3 py-1 text-xs font-medium rounded transition-colors"
          :class="activeView === v.key
            ? 'bg-sf-surface text-sf-text-1 shadow-sm'
            : 'text-sf-text-3 hover:text-sf-text-2'"
        >
          {{ v.label }}
        </button>
      </div>
    </div>

    <!-- Period stat cards -->
    <div class="grid grid-cols-2 gap-3 mb-4">
      <StatCard
        :label="`Consumed (${viewLabel})`"
        :value="periodConsumption"
        unit="kWh"
        icon="pi pi-chart-bar"
        color="red"
        :loading="loadingChart"
      />
      <StatCard
        :label="`Fed in (${viewLabel})`"
        :value="periodFeedIn"
        unit="kWh"
        icon="pi pi-chart-line"
        color="green"
        :loading="loadingChart"
      />
    </div>

    <!-- Chart -->
    <div class="bg-sf-surface rounded-sf shadow-sf p-4 mb-4">
      <div class="relative h-64">
        <div
          v-if="loadingChart"
          class="absolute inset-0 flex items-center justify-center"
        >
          <Skeleton height="100%" width="100%" />
        </div>
        <Line
          v-else-if="chartPoints.length"
          :data="chartData"
          :options="chartOptions"
          class="w-full h-full"
        />
        <div
          v-else
          class="absolute inset-0 flex flex-col items-center justify-center text-sf-text-3"
        >
          <i class="pi pi-chart-line text-3xl mb-2" />
          <p class="text-sm">No data yet for this period</p>
        </div>
      </div>
    </div>
  </AppShell>
</template>
