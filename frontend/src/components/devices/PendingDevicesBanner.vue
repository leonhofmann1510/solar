<script setup lang="ts">
import StatusDot from '@/components/shared/StatusDot.vue'
import { useDevicesStore } from '@/stores/devices'
import { computed } from 'vue'

const store = useDevicesStore()

const pendingCount = computed(() => store.pending.length)
</script>

<template>
  <div
    v-if="pendingCount > 0"
    class="bg-amber-50 border border-sf-amber-400 rounded-sf p-3 flex items-center gap-3 cursor-pointer hover:bg-amber-100 transition-colors"
  >
    <StatusDot color="amber" pulse />
    <div class="flex-1">
      <p class="text-sm font-medium text-sf-amber-600">
        {{ pendingCount }} new device{{ pendingCount === 1 ? '' : 's' }} found
      </p>
      <p class="text-xs text-sf-text-2">Confirm them to start controlling</p>
    </div>
    <i class="pi pi-chevron-down text-sf-amber-500 text-sm" />
  </div>
</template>
