import client from './client'
import type { Rule, RuleCreate } from '@/types/rule'

export const rulesApi = {
  getAll(): Promise<Rule[]> {
    return client.get('/api/rules').then((r) => r.data)
  },

  getOne(id: number): Promise<Rule> {
    return client.get(`/api/rules/${id}`).then((r) => r.data)
  },

  create(payload: RuleCreate): Promise<Rule> {
    return client.post('/api/rules', payload).then((r) => r.data)
  },

  update(id: number, payload: Partial<RuleCreate>): Promise<Rule> {
    return client.put(`/api/rules/${id}`, payload).then((r) => r.data)
  },

  remove(id: number): Promise<void> {
    return client.delete(`/api/rules/${id}`).then((r) => r.data)
  },

  toggle(id: number): Promise<Rule> {
    return client.post(`/api/rules/${id}/toggle`).then((r) => r.data)
  },

  getEvents(params?: { rule_id?: number; limit?: number }): Promise<{
    id: number
    timestamp: string
    rule_id: number
    action_taken: string
    mqtt_topic: string
    mqtt_payload: string
  }[]> {
    return client.get('/api/rules/events', { params }).then((r) => r.data)
  },
}
