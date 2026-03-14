<script setup lang="ts">
defineProps<{
  title: string
  subtitle?: string
}>()
</script>

<template>
  <div class="flex items-center justify-between mb-4">
    <div>
      <h2 class="text-lg font-semibold text-sf-text-1">{{ title }}</h2>
      <p v-if="subtitle" class="text-sm text-sf-text-2 mt-0.5">{{ subtitle }}</p>
    </div>
    <div class="flex items-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>
