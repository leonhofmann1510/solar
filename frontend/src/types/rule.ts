export type Operator = 'gt' | 'lt' | 'gte' | 'lte' | 'eq' | 'neq'
export type ConditionLogic = 'AND' | 'OR'
export type OnClearAction = 'none' | 'reverse' | 'custom'

export interface Condition {
  field: string
  operator: Operator
  value: number
}

export interface Action {
  mqtt_topic: string
  mqtt_payload: string
}

export interface Rule {
  id: number
  name: string
  enabled: boolean
  condition_logic: ConditionLogic
  conditions: Condition[]
  actions: Action[]
  on_clear_action: OnClearAction
  on_clear_payload: string | null
  cooldown_seconds: number
  last_fired_at: string | null
  state: 'idle' | 'active'
}

export type RuleCreate = Omit<Rule, 'id' | 'last_fired_at' | 'state'>
