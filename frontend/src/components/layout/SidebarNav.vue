<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useMeterStore } from '@/stores/meter'

const route = useRoute()
const meterStore = useMeterStore()

onMounted(() => meterStore.fetchStatus())

const mainItems = [
  { to: '/', label: 'Dashboard', icon: 'pi pi-home' },
  { to: '/devices', label: 'Devices', icon: 'pi pi-objects-column' },
  { to: '/rules', label: 'Rules', icon: 'pi pi-bolt' },
]

const otherItems = computed(() =>
  meterStore.status.enabled
    ? [{ to: '/meter', label: 'Smart Meter', icon: 'pi pi-chart-line' }]
    : [],
)

function isActive(to: string) {
  if (to === '/') return route.path === '/'
  return route.path.startsWith(to)
}
</script>

<template>
  <aside class="hidden md:flex flex-col w-[220px] h-screen fixed left-0 top-0 bg-sf-surface border-r border-sf-border z-30">
    <div class="px-5 py-6">
      <router-link to="/" class="text-lg font-semibold text-sf-green-600 no-underline">
        SolarFlow
      </router-link>
    </div>

    <nav class="flex-1 px-3 space-y-1 overflow-y-auto">
      <router-link
        v-for="item in mainItems"
        :key="item.to"
        :to="item.to"
        class="flex items-center gap-3 px-3 py-2.5 rounded-sf-sm text-sm font-medium no-underline transition-colors"
        :class="isActive(item.to)
          ? 'bg-sf-green-50 text-sf-green-700'
          : 'text-sf-text-2 hover:bg-slate-50 hover:text-sf-text-1'"
      >
        <i :class="item.icon" class="text-base" />
        {{ item.label }}
      </router-link>

      <template v-if="otherItems.length">
        <div class="pt-4 pb-1 px-3">
          <span class="text-[10px] font-semibold uppercase tracking-widest text-sf-text-3">Other</span>
        </div>
        <router-link
          v-for="item in otherItems"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-3 px-3 py-2.5 rounded-sf-sm text-sm font-medium no-underline transition-colors"
          :class="isActive(item.to)
            ? 'bg-sf-green-50 text-sf-green-700'
            : 'text-sf-text-2 hover:bg-slate-50 hover:text-sf-text-1'"
        >
          <i :class="item.icon" class="text-base" />
          {{ item.label }}
        </router-link>
      </template>
    </nav>
  </aside>
</template>
