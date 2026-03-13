<script setup lang="ts">
import { watch } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useReadingsStore } from '@/stores/readings'

const { latestReading } = useWebSocket()
const readingsStore = useReadingsStore()

watch(latestReading, (reading) => {
  if (reading) readingsStore.pushLiveReading(reading)
})
</script>

<template>
  <router-view />
</template>
