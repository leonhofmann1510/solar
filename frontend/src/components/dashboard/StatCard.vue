<script setup lang="ts">
import Skeleton from 'primevue/skeleton'

defineProps<{
  label: string
  value?: string | number | null
  unit?: string
  icon?: string
  color?: 'green' | 'amber' | 'red' | 'neutral'
  loading?: boolean
}>()
</script>

<template>
  <div class="bg-sf-surface rounded-sf shadow-sf p-4 relative">
    <div class="flex items-start justify-between">
      <p class="text-xs font-medium uppercase tracking-wider text-sf-text-2 mb-2">
        {{ label }}
      </p>
      <span
        v-if="icon"
        class="w-8 h-8 rounded-full flex items-center justify-center text-sm"
        :class="{
          'bg-sf-green-50 text-sf-green-600': color === 'green',
          'bg-amber-50 text-sf-amber-600': color === 'amber',
          'bg-red-50 text-sf-red-500': color === 'red',
          'bg-slate-50 text-sf-text-2': color === 'neutral' || !color,
        }"
      >
        <i :class="icon" />
      </span>
    </div>

    <Skeleton v-if="loading" width="60%" height="2rem" />
    <template v-else>
      <div class="flex items-baseline gap-1">
        <span class="text-2xl font-semibold text-sf-text-1">
          {{ value ?? '' }}
        </span>
        <span v-if="unit && value != null" class="text-sm text-sf-text-2">
          {{ unit }}
        </span>
      </div>
    </template>

    <slot />
  </div>
</template>
