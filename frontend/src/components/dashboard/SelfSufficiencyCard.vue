<script setup lang="ts">
import { onMounted, ref } from 'vue'
import Skeleton from 'primevue/skeleton'
import { getSelfSufficiency } from '@/api/stats'
import type { SelfSufficiencyOut } from '@/types/stats'

const data = ref<SelfSufficiencyOut | null>(null)
const loading = ref(true)

onMounted(async () => {
  try {
    data.value = await getSelfSufficiency()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="bg-sf-surface rounded-sf shadow-sf p-4 relative">
    <div class="flex items-start justify-between">
      <p class="text-xs font-medium uppercase tracking-wider text-sf-text-2 mb-2">Self-Sufficiency</p>
      <span class="w-8 h-8 rounded-full flex items-center justify-center text-sm bg-sf-green-50 text-sf-green-600">
        <i class="pi pi-chart-pie" />
      </span>
    </div>

    <Skeleton v-if="loading" width="60%" height="2rem" />
    <template v-else>
      <div class="flex items-baseline gap-1">
        <span class="text-2xl font-semibold text-sf-text-1">
          {{ data != null ? data.rate_pct.toFixed(1) : '—' }}
        </span>
        <span v-if="data != null" class="text-sm text-sf-text-2">%</span>
      </div>
      <p class="text-xs text-sf-text-2 mt-0.5">Last 365 days</p>
      <span
        v-if="data?.week_delta_pct != null"
        class="inline-block mt-1.5 text-xs font-medium px-1.5 py-0.5 rounded"
        :class="data.week_delta_pct >= 0 ? 'bg-sf-green-50 text-sf-green-600' : 'bg-red-50 text-red-500'"
      >
        {{ data.week_delta_pct >= 0 ? '+' : '' }}{{ data.week_delta_pct.toFixed(1) }}% this week
      </span>
    </template>
  </div>
</template>
