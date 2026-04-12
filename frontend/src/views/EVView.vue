<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  Tooltip,
  Legend,
  type TooltipItem,
} from 'chart.js'
import { Bar, Doughnut } from 'vue-chartjs'
import AppShell from '@/components/layout/AppShell.vue'
import SectionHeader from '@/components/shared/SectionHeader.vue'
import StatCard from '@/components/dashboard/StatCard.vue'
import { useEVStore } from '@/stores/ev'
import { getEVSessions } from '@/api/ev'
import type { EVSession } from '@/types/ev'

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, Tooltip, Legend)

const evStore = useEVStore()

const sessions = ref<EVSession[]>([])
const loading = ref(true)

// ── Live ticker ────────────────────────────────────────────────────────────

const now = ref(Date.now())
let ticker: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  ticker = setInterval(() => { now.value = Date.now() }, 1000)
  await Promise.all([evStore.fetchStatus(), evStore.fetchSummary()])
  sessions.value = await getEVSessions(50)
  loading.value = false
})

onUnmounted(() => {
  if (ticker) clearInterval(ticker)
})

// ── Live charging banner ───────────────────────────────────────────────────

const activeSession = computed(() => evStore.status.active_session)

const liveDurationSeconds = computed(() => {
  if (!activeSession.value?.started_at) return 0
  return Math.max(0, Math.floor((now.value - new Date(activeSession.value.started_at).getTime()) / 1000))
})

const liveKwh = computed(() => {
  if (!activeSession.value) return 0
  return activeSession.value.charging_power_kw * (liveDurationSeconds.value / 3600)
})

function formatSeconds(total: number): string {
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

// ── Summary stats ─────────────────────────────────────────────────────────

const summary = computed(() => evStore.summary)

const weekKwhDiff = computed(() => {
  if (!summary.value) return null
  const diff = summary.value.this_week_kwh - summary.value.last_week_kwh
  return diff >= 0 ? `+${diff.toFixed(1)}` : diff.toFixed(1)
})

// ── Bar chart: kWh per day last 7 days ────────────────────────────────────

const last7Days = computed(() => {
  const now = new Date()
  const days: string[] = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now)
    d.setDate(d.getDate() - i)
    days.push(d.toISOString().slice(0, 10))
  }
  return days
})

const barLabels = computed(() =>
  last7Days.value.map((d) => {
    const dt = new Date(d)
    return dt.toLocaleDateString('en', { weekday: 'short', day: 'numeric' })
  }),
)

function kwhForDay(isoDate: string, type: 'solar' | 'grid'): number {
  return sessions.value
    .filter((s) => s.ended_at && s.ended_at.slice(0, 10) === isoDate)
    .reduce((sum, s) => sum + (type === 'solar' ? s.kwh_solar : s.kwh_grid), 0)
}

const barChartData = computed(() => ({
  labels: barLabels.value,
  datasets: [
    {
      label: 'Solar',
      data: last7Days.value.map((d) => kwhForDay(d, 'solar')),
      backgroundColor: '#22c55e',
      borderRadius: 3,
    },
    {
      label: 'Grid',
      data: last7Days.value.map((d) => kwhForDay(d, 'grid')),
      backgroundColor: '#64748b',
      borderRadius: 3,
    },
  ],
}))

const barChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'top' as const, labels: { color: '#64748b', font: { size: 12 }, boxWidth: 12, padding: 16 } },
    tooltip: {
      callbacks: {
        label: (ctx: TooltipItem<'bar'>) =>
          ` ${ctx.dataset.label}: ${(ctx.parsed as { y: number }).y.toFixed(2)} kWh`,
      },
    },
  },
  scales: {
    x: { stacked: true, grid: { color: 'rgba(100,116,139,0.08)' }, ticks: { color: '#94a3b8', font: { size: 11 } } },
    y: { stacked: true, grid: { color: 'rgba(100,116,139,0.08)' }, ticks: { color: '#94a3b8', font: { size: 11 }, callback: (v: number | string) => `${Number(v).toFixed(1)}` } },
  },
}

// ── Doughnut: solar vs grid all sessions ─────────────────────────────────

const totalSolar = computed(() => sessions.value.reduce((s, r) => s + r.kwh_solar, 0))
const totalGrid = computed(() => sessions.value.reduce((s, r) => s + r.kwh_grid, 0))
const hasDoughnutData = computed(() => totalSolar.value + totalGrid.value > 0)

const doughnutData = computed(() => ({
  labels: ['Solar', 'Grid'],
  datasets: [{
    data: [totalSolar.value, totalGrid.value],
    backgroundColor: ['#22c55e', '#64748b'],
    borderWidth: 0,
  }],
}))

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom' as const, labels: { color: '#64748b', font: { size: 12 }, boxWidth: 12, padding: 16 } },
    tooltip: {
      callbacks: {
        label: (ctx: TooltipItem<'doughnut'>) =>
          ` ${ctx.label}: ${(ctx.parsed as number).toFixed(2)} kWh`,
      },
    },
  },
}

// ── Session table helpers ─────────────────────────────────────────────────

function sessionDate(s: EVSession): string {
  return new Date(s.started_at).toLocaleDateString('en', { day: '2-digit', month: 'short', year: 'numeric' })
}

function sessionDuration(s: EVSession): string {
  return formatSeconds(s.duration_solar_seconds + s.duration_grid_seconds)
}

function sessionKm(s: EVSession): string {
  return (s.kwh_total * s.efficiency_km_per_kwh).toFixed(0)
}
</script>

<template>
  <AppShell>
    <div class="mb-6">
      <h1 class="text-xl font-semibold text-sf-text-1">EV Charging</h1>
      <p class="text-sm text-sf-text-2 mt-0.5">Solar vs grid charging statistics</p>
    </div>

    <!-- Status banner -->
    <div
      v-if="activeSession"
      class="mb-6 rounded-sf p-4 flex items-center gap-3 bg-sf-green-50 border border-sf-green-200"
    >
      <span class="w-2.5 h-2.5 rounded-full bg-sf-green-500 animate-pulse" />
      <div class="flex-1">
        <p class="text-sm font-semibold text-sf-green-700">Currently charging</p>
        <p class="text-xs text-sf-green-600 mt-0.5">
          Duration: {{ formatSeconds(liveDurationSeconds) }}
          &nbsp;·&nbsp;
          Est. {{ liveKwh.toFixed(2) }} kWh
        </p>
      </div>
    </div>
    <div
      v-else-if="!loading"
      class="mb-6 rounded-sf p-4 flex items-center gap-3 bg-slate-50 border border-sf-border"
    >
      <span class="w-2.5 h-2.5 rounded-full bg-slate-300" />
      <p class="text-sm text-sf-text-2">Not charging</p>
    </div>

    <!-- Stat cards -->
    <SectionHeader title="This week" />
    <div class="grid grid-cols-2 gap-3 mb-6">
      <StatCard
        label="Energy charged"
        :value="summary ? summary.this_week_kwh.toFixed(1) : null"
        unit="kWh"
        icon="pi pi-bolt"
        color="green"
        :loading="loading"
      />
      <StatCard
        label="vs last week"
        :value="weekKwhDiff"
        unit="kWh"
        icon="pi pi-chart-line"
        color="neutral"
        :loading="loading"
      />
      <StatCard
        label="Distance equiv."
        :value="summary ? summary.this_week_km.toFixed(0) : null"
        unit="km"
        icon="pi pi-car"
        color="green"
        :loading="loading"
      />
      <StatCard
        label="Total saved vs gas"
        :value="summary ? summary.total_savings_eur.toFixed(2) : null"
        unit="€"
        icon="pi pi-euro"
        color="amber"
        :loading="loading"
      />
    </div>

    <!-- Charts row -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
      <!-- Bar chart -->
      <div class="bg-sf-surface rounded-sf shadow-sf p-4">
        <p class="text-xs font-semibold uppercase tracking-wider text-sf-text-2 mb-3">kWh per day (last 7 days)</p>
        <div class="relative h-48">
          <Bar :data="barChartData" :options="barChartOptions" class="w-full h-full" />
        </div>
      </div>

      <!-- Doughnut chart -->
      <div class="bg-sf-surface rounded-sf shadow-sf p-4">
        <p class="text-xs font-semibold uppercase tracking-wider text-sf-text-2 mb-3">Solar vs Grid (all sessions)</p>
        <div class="relative h-48 flex items-center justify-center">
          <Doughnut v-if="hasDoughnutData" :data="doughnutData" :options="doughnutOptions" class="h-full" />
          <div v-else class="flex flex-col items-center text-sf-text-3">
            <i class="pi pi-chart-pie text-3xl mb-2" />
            <p class="text-sm">No sessions yet</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Sessions log -->
    <SectionHeader :title="`Sessions (${sessions.length})`" />
    <div v-if="sessions.length" class="bg-sf-surface rounded-sf shadow-sf overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-sf-border text-left">
              <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-sf-text-2">Date</th>
              <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-sf-text-2">Duration</th>
              <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-sf-text-2 text-right">kWh</th>
              <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-sf-green-600 text-right">Solar</th>
              <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-sf-text-2 text-right">Grid</th>
              <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-sf-text-2 text-right">km</th>
              <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-sf-text-2 text-right">Cost</th>
              <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-sf-amber-600 text-right">Saved</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in sessions"
              :key="s.id"
              class="border-b border-sf-border last:border-0 hover:bg-slate-50 transition-colors"
            >
              <td class="px-4 py-2.5 text-sf-text-1">{{ sessionDate(s) }}</td>
              <td class="px-4 py-2.5 text-sf-text-2">{{ sessionDuration(s) }}</td>
              <td class="px-4 py-2.5 text-sf-text-1 text-right font-medium">{{ s.kwh_total.toFixed(2) }}</td>
              <td class="px-4 py-2.5 text-sf-green-600 text-right">{{ s.kwh_solar.toFixed(2) }}</td>
              <td class="px-4 py-2.5 text-sf-text-2 text-right">{{ s.kwh_grid.toFixed(2) }}</td>
              <td class="px-4 py-2.5 text-sf-text-2 text-right">{{ sessionKm(s) }}</td>
              <td class="px-4 py-2.5 text-sf-text-1 text-right">{{ s.cost_eur.toFixed(2) }} €</td>
              <td class="px-4 py-2.5 text-right font-medium" :class="s.savings_vs_gas_eur >= 0 ? 'text-sf-green-600' : 'text-sf-red-500'">
                {{ s.savings_vs_gas_eur >= 0 ? '+' : '' }}{{ s.savings_vs_gas_eur.toFixed(2) }} €
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <div v-else-if="!loading" class="bg-sf-surface rounded-sf shadow-sf p-8 text-center text-sf-text-3">
      <i class="pi pi-car text-3xl mb-2" />
      <p class="text-sm">No completed sessions yet</p>
    </div>
  </AppShell>
</template>
