<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useMeterStore } from '@/stores/meter'

const route = useRoute()
const meterStore = useMeterStore()

onMounted(() => meterStore.fetchStatus())

const navItems = computed(() => [
  { to: '/', label: 'Dashboard', icon: 'pi pi-home' },
  { to: '/devices', label: 'Devices', icon: 'pi pi-objects-column' },
  { to: '/rules', label: 'Rules', icon: 'pi pi-bolt' },
  ...(meterStore.status.enabled
    ? [{ to: '/meter', label: 'Meter', icon: 'pi pi-chart-line' }]
    : []),
])

function isActive(to: string) {
  if (to === '/') return route.path === '/'
  return route.path.startsWith(to)
}
</script>

<template>
  <nav class="md:hidden fixed bottom-0 left-0 right-0 bg-sf-surface border-t border-sf-border z-30 safe-bottom">
    <div class="flex items-center justify-around py-2 pb-[max(0.5rem,env(safe-area-inset-bottom))]">
      <router-link
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="flex flex-col items-center gap-0.5 py-1 px-3 no-underline transition-colors"
        :class="isActive(item.to)
          ? 'text-sf-green-600'
          : 'text-sf-text-3'"
      >
        <i :class="item.icon" class="text-lg" />
        <span class="text-[10px] font-medium">{{ item.label }}</span>
      </router-link>
    </div>
  </nav>
</template>
