<script setup lang="ts">
defineProps<{
  color?: 'green' | 'amber' | 'red' | 'grey'
  label?: string
  pulse?: boolean
}>()
</script>

<template>
  <span class="inline-flex items-center gap-1.5">
    <span
      class="inline-block w-2 h-2 rounded-full shrink-0"
      :class="{
        'bg-sf-green-500': color === 'green',
        'bg-sf-amber-500': color === 'amber',
        'bg-sf-red-500': color === 'red',
        'bg-sf-text-3': color === 'grey' || !color,
        'animate-pulse': pulse,
      }"
    />
    <span v-if="label" class="text-xs font-medium" :class="{
      'text-sf-green-600': color === 'green',
      'text-sf-amber-600': color === 'amber',
      'text-sf-red-500': color === 'red',
      'text-sf-text-3': color === 'grey' || !color,
    }">{{ label }}</span>
  </span>
</template>
