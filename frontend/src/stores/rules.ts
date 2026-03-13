import { defineStore } from 'pinia'
import { ref } from 'vue'
import { rulesApi } from '@/api/rules'
import type { Rule, RuleCreate } from '@/types/rule'

export const useRulesStore = defineStore('rules', () => {
  const rules = ref<Rule[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchAll() {
    loading.value = true
    error.value = null
    try {
      rules.value = await rulesApi.getAll()
    } catch (e: any) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function create(payload: RuleCreate) {
    const rule = await rulesApi.create(payload)
    rules.value.push(rule)
    return rule
  }

  async function update(id: number, payload: Partial<RuleCreate>) {
    const updated = await rulesApi.update(id, payload)
    const idx = rules.value.findIndex((r) => r.id === id)
    if (idx !== -1) rules.value[idx] = updated
    return updated
  }

  async function remove(id: number) {
    await rulesApi.remove(id)
    rules.value = rules.value.filter((r) => r.id !== id)
  }

  async function toggle(id: number) {
    const updated = await rulesApi.toggle(id)
    const idx = rules.value.findIndex((r) => r.id === id)
    if (idx !== -1) rules.value[idx] = updated
  }

  return { rules, loading, error, fetchAll, create, update, remove, toggle }
})
