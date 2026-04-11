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
import SectionHeader from '@/components/shared/SectionHeader.vue'
import { getStatsChart } from '@/api/stats'
import type { StatChartPoint, StatsView } from '@/types/stats'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend)

const views: { key: StatsView; label: string }[] = [
  { key: 'day', label: 'Day' },
  { key: 'week', label: 'Week' },
  { key: 'month', label: 'Month' },
  { key: 'year', label: 'Year' },
]

const activeView = ref<StatsView>('week')
const chartPoints = ref<StatChartPoint[]>([])
const loadingChart = ref(false)

async function loadChart() {
  loadingChart.value = true
  try {
    chartPoints.value = await getStatsChart(activeView.value)
  } finally {
    loadingChart.value = false
  }
}

onMounted(loadChart)
watch(activeView, loadChart)

const chartData = computed(() => ({
  labels: chartPoints.value.map((p) => p.label),
  datasets: [
    {
      label: 'Yield',
      data: chartPoints.value.map((p) => p.yield_kwh),
      borderColor: '#22c55e',
      backgroundColor: 'rgba(34,197,94,0.10)',
      fill: true,
      tension: 0.35,
      pointRadius: chartPoints.value.length > 48 ? 0 : 3,
    },
    {
      label: 'Self-use',
      data: chartPoints.value.map((p) => p.self_consumption_kwh),
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59,130,246,0.10)',
      fill: true,
      tension: 0.35,
      pointRadius: chartPoints.value.length > 48 ? 0 : 3,
    },
    {
      label: 'Feed-in',
      data: chartPoints.value.map((p) => p.feed_in_kwh),
      borderColor: '#a855f7',
      backgroundColor: 'rgba(168,85,247,0.10)',
      fill: true,
      tension: 0.35,
      pointRadius: chartPoints.value.length > 48 ? 0 : 3,
    },
    {
      label: 'Grid Buy',
      data: chartPoints.value.map((p) => p.grid_buy_kwh),
      borderColor: '#ef4444',
      backgroundColor: 'rgba(239,68,68,0.10)',
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
          ` ${ctx.dataset.label ?? ''}: ${(ctx.parsed as { y: number }).y.toFixed(2)} kWh`,
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
        callback: (v: number | string) => `${Number(v).toFixed(1)} kWh`,
      },
    },
  },
}))
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-3">
      <SectionHeader title="Energy History" class="mb-0" />
      <div class="flex gap-1 bg-slate-100 rounded-sf p-1">
        <button
          v-for="v in views"
          :key="v.key"
          @click="activeView = v.key"
          class="px-3 py-1 text-xs font-medium rounded transition-colors"
          :class="
            activeView === v.key
              ? 'bg-sf-surface text-sf-text-1 shadow-sm'
              : 'text-sf-text-3 hover:text-sf-text-2'
          "
        >
          {{ v.label }}
        </button>
      </div>
    </div>

    <div class="bg-sf-surface rounded-sf shadow-sf p-4">
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
  </div>
</template>
