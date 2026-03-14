<script setup lang="ts">
import { computed } from 'vue'
import StatCard from './StatCard.vue'

const props = defineProps<{
  gridPowerW: number | null
  loading?: boolean
}>()

const display = computed(() => {
  if (props.gridPowerW == null) return { value: null, label: '', color: 'neutral' as const, arrow: '' }
  const absKw = (Math.abs(props.gridPowerW) / 1000).toFixed(1)
  if (props.gridPowerW > 50) {
    return { value: absKw, label: 'exporting', color: 'green' as const, arrow: '\u2191' }
  }
  if (props.gridPowerW < -50) {
    return { value: absKw, label: 'importing', color: 'amber' as const, arrow: '\u2193' }
  }
  return { value: '0.0', label: 'balanced', color: 'neutral' as const, arrow: '\u2014' }
})
</script>

<template>
  <StatCard
    label="Grid"
    icon="pi pi-arrows-v"
    :color="display.color"
    :loading="loading"
  >
    <template v-if="!loading">
      <div class="flex items-baseline gap-1.5">
        <span
          class="text-lg font-medium"
          :class="{
            'text-sf-green-600': display.color === 'green',
            'text-sf-amber-600': display.color === 'amber',
            'text-sf-text-2': display.color === 'neutral',
          }"
        >{{ display.arrow }}</span>
        <span class="text-2xl font-semibold text-sf-text-1">{{ display.value ?? '—' }}</span>
        <span v-if="display.value" class="text-sm text-sf-text-2">kW</span>
      </div>
      <p
        v-if="display.value"
        class="text-xs mt-1"
        :class="{
          'text-sf-green-600': display.color === 'green',
          'text-sf-amber-600': display.color === 'amber',
          'text-sf-text-3': display.color === 'neutral',
        }"
      >{{ display.label }}</p>
    </template>
  </StatCard>
</template>
