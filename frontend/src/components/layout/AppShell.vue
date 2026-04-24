<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import SidebarNav from './SidebarNav.vue'
import BottomTabBar from './BottomTabBar.vue'
import SettingsModal from './SettingsModal.vue'
import Button from 'primevue/button'

const settingsVisible = ref(false)
const router = useRouter()
</script>

<template>
  <div class="min-h-screen bg-sf-bg">
    <SidebarNav />

    <!-- Mobile header -->
    <header class="md:hidden fixed top-0 left-0 right-0 bg-sf-surface border-b border-sf-border z-30 px-4 h-14 flex items-center justify-between">
      <span class="text-base font-semibold text-sf-green-600">SolarFlow</span>
      <div class="flex gap-1">
        <Button
          icon="pi pi-database"
          text
          rounded
          severity="secondary"
          @click="router.push('/data')"
          aria-label="Data Management"
        />
        <Button
          icon="pi pi-cog"
          text
          rounded
          severity="secondary"
          @click="settingsVisible = true"
          aria-label="Settings"
        />
      </div>
    </header>

    <!-- Desktop header bar (settings button only) -->
    <div class="hidden md:flex fixed top-0 left-[220px] right-0 h-14 bg-sf-surface border-b border-sf-border z-20 px-6 items-center justify-end">
      <div class="flex gap-1">
        <Button
          icon="pi pi-database"
          text
          rounded
          severity="secondary"
          @click="router.push('/data')"
          aria-label="Data Management"
        />
        <Button
          icon="pi pi-cog"
          text
          rounded
          severity="secondary"
          @click="settingsVisible = true"
          aria-label="Settings"
        />
      </div>
    </div>

    <!-- Main content area -->
    <main
      class="pt-14 pb-20 md:pb-6 md:pl-[220px] md:pt-14"
    >
      <div class="px-4 py-4 md:px-6 md:py-6 max-w-6xl mx-auto">
        <slot />
      </div>
    </main>

    <BottomTabBar />

    <SettingsModal v-model:visible="settingsVisible" />
  </div>
</template>
