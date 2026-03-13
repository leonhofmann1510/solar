export interface InverterReading {
  id: number
  timestamp: string
  inverter_id: 'inv1' | 'inv2'
  pv_power_w: number
  pv_string1_w: number
  pv_string2_w: number
  battery_soc_pct: number | null
  battery_power_w: number | null
  grid_power_w: number
  house_load_w: number
  pv_yield_today_kwh: number
  feed_in_today_kwh: number
  grid_buy_today_kwh: number
  inverter_temp_c: number
  grid_frequency_hz: number
}
