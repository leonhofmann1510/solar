export type Operator = 'gt' | 'lt' | 'gte' | 'lte' | 'eq' | 'neq'
export type ConditionLogic = 'AND' | 'OR'
export type OnClearAction = 'none' | 'reverse' | 'custom'

export interface Condition {
  field: string
  operator: Operator
  value: number
}

// MQTT-based action (raw topic/payload)
export interface MqttAction {
  type: 'mqtt'
  mqtt_topic: string
  mqtt_payload: string
}

// Device-based action (works with any protocol: Tuya, MQTT devices, etc.)
export interface DeviceAction {
  type: 'device'
  device_id: number
  capability_key: string
  value: boolean | number | string
}

export type Action = MqttAction | DeviceAction

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
