<script setup lang="ts">
import { computed } from 'vue'
import StatCard from './StatCard.vue'
import ProgressBar from 'primevue/progressbar'

const props = defineProps<{
  soc: number | null
  power: number | null
  loading?: boolean
}>()

const colorClass = computed(() => {
  if (props.soc == null) return 'neutral'
  if (props.soc >= 80) return 'green'
  if (props.soc >= 20) return 'amber'
  return 'red'
})

const progressColor = computed(() => {
  if (props.soc == null) return undefined
  if (props.soc >= 80) return '#22c55e'
  if (props.soc >= 20) return '#f59e0b'
  return '#ef4444'
})

const powerLabel = computed(() => {
  if (props.power == null) return ''
  if (props.power > 0) return 'Charging'
  if (props.power < 0) return 'Discharging'
  return 'Idle'
})
</script>

<template>
  <StatCard
    label="Battery"
    :value="soc != null ? `${soc}` : null"
    unit="%"
    icon="pi pi-bolt"
    :color="colorClass"
    :loading="loading"
  >
    <div v-if="!loading && soc != null" class="mt-3">
      <ProgressBar
        :value="soc"
        :showValue="false"
        style="height: 6px; border-radius: 3px;"
        :pt="{ value: { style: { background: progressColor, borderRadius: '3px' } } }"
      />
      <p v-if="power != null" class="text-xs text-sf-text-3 mt-1.5">
        {{ Math.abs(power) }} W {{ powerLabel }}
      </p>
    </div>
  </StatCard>
</template>
