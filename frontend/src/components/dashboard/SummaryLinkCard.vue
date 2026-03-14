<script setup lang="ts">
import Tag from 'primevue/tag'

defineProps<{
  icon: string
  label: string
  total: number
  alertCount?: number
  alertLabel?: string
  to: string
}>()
</script>

<template>
  <router-link
    :to="to"
    class="block bg-sf-surface rounded-sf shadow-sf p-4 hover:shadow-sf-md transition-shadow cursor-pointer no-underline"
  >
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <span class="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center text-sf-text-2">
          <i :class="icon" class="text-lg" />
        </span>
        <div>
          <p class="text-sm font-medium text-sf-text-1">{{ label }}</p>
          <p class="text-xs text-sf-text-3">{{ total }} total</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <Tag
          v-if="alertCount && alertCount > 0"
          :value="`${alertCount} ${alertLabel || 'offline'}`"
          severity="warn"
          class="text-xs"
        />
        <i class="pi pi-chevron-right text-sf-text-3 text-sm" />
      </div>
    </div>
  </router-link>
</template>
