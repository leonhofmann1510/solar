<script setup lang="ts">
defineProps<{
  icon?: string
  title: string
  message?: string
  actionLabel?: string
}>()

defineEmits<{
  action: []
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center py-12 px-6 text-center">
    <i
      v-if="icon"
      :class="icon"
      class="text-4xl text-sf-text-3 mb-4"
    />
    <h3 class="text-base font-medium text-sf-text-1 mb-1">{{ title }}</h3>
    <p v-if="message" class="text-sm text-sf-text-2 max-w-xs">{{ message }}</p>
    <button
      v-if="actionLabel"
      @click="$emit('action')"
      class="mt-4 px-4 py-2 rounded-sf-sm bg-sf-green-500 text-white text-sm font-medium
             hover:bg-sf-green-600 transition-colors"
    >
      {{ actionLabel }}
    </button>
  </div>
</template>
