export interface DeviceCapability {
  id: number
  device_id: number
  key: string
  display_name: string
  capability_type: 'state' | 'action' | 'both'
  data_type: 'boolean' | 'integer' | 'float' | 'string'
  min_value: number | null
  max_value: number | null
  unit: string | null
  mqtt_command_topic: string | null
  mqtt_state_topic: string | null
  tuya_dp_id: number | null
}

export interface DeviceState {
  capability_key: string
  value_boolean: boolean | null
  value_numeric: number | null
  value_string: string | null
  updated_at: string
}

export interface Device {
  id: number
  name: string
  protocol: string
  confirmed: boolean
  enabled: boolean
  room: string | null
  raw_id: string
  ip_address: string | null
  mqtt_base_topic: string | null
  first_seen_at: string
  last_seen_at: string
  capabilities: DeviceCapability[]
  states: DeviceState[]
}

export interface DeviceConfirm {
  name: string
  room?: string | null
}

export interface DeviceUpdate {
  name?: string
  room?: string | null
  enabled?: boolean
}

export interface DeviceActionRequest {
  capability_key: string
  value: boolean | number | string
}
