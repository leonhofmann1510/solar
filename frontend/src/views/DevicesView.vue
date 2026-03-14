<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useDevicesStore } from '@/stores/devices'
import { devicesApi } from '@/api/devices'
import type { Device, DeviceCapability, DeviceState } from '@/types/device'

const store = useDevicesStore()

const actionDeviceId = ref<number | null>(null)
const actionCapabilityKey = ref('')
const actionValue = ref('')
const actionResult = ref<string | null>(null)
const actionError = ref<string | null>(null)

const confirmName = ref('')
const confirmRoom = ref('')
const confirmingId = ref<number | null>(null)

const discoveringMdns = ref(false)
const scanningTuya = ref(false)
const discoveryMessage = ref<string | null>(null)

onMounted(async () => {
  await Promise.all([store.fetchAll(), store.fetchPending()])
})

function getStateValue(device: Device, capKey: string): string {
  const state = device.states.find((s) => s.capability_key === capKey)
  if (!state) return '—'
  if (state.value_boolean !== null) return String(state.value_boolean)
  if (state.value_numeric !== null) return String(state.value_numeric)
  if (state.value_string !== null) return state.value_string
  return '—'
}

async function sendAction() {
  if (actionDeviceId.value === null || !actionCapabilityKey.value) return
  actionResult.value = null
  actionError.value = null

  let parsedValue: boolean | number | string = actionValue.value
  if (actionValue.value === 'true') parsedValue = true
  else if (actionValue.value === 'false') parsedValue = false
  else if (!isNaN(Number(actionValue.value)) && actionValue.value.trim() !== '') {
    parsedValue = Number(actionValue.value)
  }

  try {
    const result = await store.sendAction(actionDeviceId.value, {
      capability_key: actionCapabilityKey.value,
      value: parsedValue,
    })
    actionResult.value = JSON.stringify(result, null, 2)
  } catch (e: any) {
    actionError.value = e.response?.data?.detail || e.message
  }
}

function startConfirm(device: Device) {
  confirmingId.value = device.id
  confirmName.value = device.name
  confirmRoom.value = ''
}

async function submitConfirm() {
  if (confirmingId.value === null) return
  try {
    await store.confirm(confirmingId.value, {
      name: confirmName.value,
      room: confirmRoom.value || null,
    })
    confirmingId.value = null
  } catch (e: any) {
    alert('Confirm failed: ' + (e.response?.data?.detail || e.message))
  }
}

async function deleteDevice(id: number) {
  if (!window.confirm('Delete this device?')) return
  await store.remove(id)
}

async function toggleEnabled(device: Device) {
  await store.update(device.id, { enabled: !device.enabled })
}

async function runDiscoverMdns() {
  discoveringMdns.value = true
  discoveryMessage.value = null
  try {
    const result = await store.discoverMdns()
    discoveryMessage.value = `mDNS: ${result.discovered} new device(s) found`
  } catch (e: any) {
    discoveryMessage.value = `mDNS error: ${e.response?.data?.detail || e.message}`
  } finally {
    discoveringMdns.value = false
  }
}

async function runScanTuya() {
  scanningTuya.value = true
  discoveryMessage.value = null
  try {
    const result = await store.scanTuyaNetwork()
    discoveryMessage.value = `Tuya scan: ${result.scanned} device(s) found on network, ${result.updated} IP(s) updated`
  } catch (e: any) {
    discoveryMessage.value = `Tuya scan error: ${e.response?.data?.detail || e.message}`
  } finally {
    scanningTuya.value = false
  }
}

async function reload() {
  await Promise.all([store.fetchAll(), store.fetchPending()])
}

const readDeviceId = ref<number | null>(null)
const readResult = ref<Record<string, unknown> | null>(null)
const readError = ref<string | null>(null)
const reading = ref(false)

async function readRawDps() {
  if (readDeviceId.value === null) return
  readResult.value = null
  readError.value = null
  reading.value = true
  try {
    const result = await devicesApi.readRawDps(readDeviceId.value)
    readResult.value = result.raw_dps
  } catch (e: any) {
    readError.value = e.response?.data?.detail || e.message
  } finally {
    reading.value = false
  }
}
</script>

<template>
  <div>
    <h1>Devices</h1>

    <!-- Discovery -->
    <section>
      <h2>Discovery</h2>
      <p>To link Tuya devices, go to <router-link to="/settings">Settings</router-link>.</p>
      <button @click="runDiscoverMdns" :disabled="discoveringMdns">
        {{ discoveringMdns ? 'Scanning mDNS...' : 'Discover mDNS' }}
      </button>
      <button @click="runScanTuya" :disabled="scanningTuya">
        {{ scanningTuya ? 'Scanning network...' : 'Scan Tuya IPs' }}
      </button>
      <button @click="reload">Reload</button>
      <p>Z2M and Shelly/Tasmota devices are discovered automatically via MQTT.</p>
      <p v-if="discoveryMessage"><strong>{{ discoveryMessage }}</strong></p>
    </section>

    <!-- Pending Devices -->
    <section>
      <h2>Pending Devices ({{ store.pending.length }})</h2>
      <p v-if="store.pending.length === 0">No pending devices.</p>
      <table v-else>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Protocol</th>
            <th>Raw ID</th>
            <th>IP</th>
            <th>Capabilities</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="device in store.pending" :key="device.id">
            <td>{{ device.id }}</td>
            <td>{{ device.name }}</td>
            <td>{{ device.protocol }}</td>
            <td>{{ device.raw_id }}</td>
            <td>{{ device.ip_address || '—' }}</td>
            <td>{{ device.capabilities.map(c => c.key).join(', ') || '—' }}</td>
            <td>
              <button @click="startConfirm(device)">Confirm</button>
              <button @click="deleteDevice(device.id)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Confirm form -->
      <div v-if="confirmingId !== null">
        <h3>Confirm Device #{{ confirmingId }}</h3>
        <label>Name: <input v-model="confirmName" /></label>
        <label>Room: <input v-model="confirmRoom" placeholder="optional" /></label>
        <button @click="submitConfirm">Submit</button>
        <button @click="confirmingId = null">Cancel</button>
      </div>
    </section>

    <!-- Confirmed Devices -->
    <section>
      <h2>Confirmed Devices ({{ store.devices.length }})</h2>
      <p v-if="store.loading">Loading...</p>
      <p v-if="store.error">Error: {{ store.error }}</p>
      <p v-if="!store.loading && store.devices.length === 0">No confirmed devices.</p>

      <div v-for="device in store.devices" :key="device.id">
        <h3>
          {{ device.name }}
          <small>({{ device.protocol }}, ID={{ device.id }})</small>
        </h3>
        <p>
          Raw ID: {{ device.raw_id }} |
          IP: {{ device.ip_address || '—' }} |
          Enabled: {{ device.enabled }} |
          Room: {{ device.room || '—' }} |
          Last seen: {{ device.last_seen_at }}
        </p>
        <button @click="toggleEnabled(device)">
          {{ device.enabled ? 'Disable' : 'Enable' }}
        </button>
        <button @click="deleteDevice(device.id)">Delete</button>

        <h4>Capabilities</h4>
        <table v-if="device.capabilities.length > 0">
          <thead>
            <tr>
              <th>Key</th>
              <th>Name</th>
              <th>Type</th>
              <th>Data Type</th>
              <th>Unit</th>
              <th>Range</th>
              <th>Current Value</th>
              <th>Tuya DP</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="cap in device.capabilities" :key="cap.key">
              <td>{{ cap.key }}</td>
              <td>{{ cap.display_name }}</td>
              <td>{{ cap.capability_type }}</td>
              <td>{{ cap.data_type }}</td>
              <td>{{ cap.unit || '—' }}</td>
              <td>
                <span v-if="cap.min_value !== null || cap.max_value !== null">
                  {{ cap.min_value ?? '' }} — {{ cap.max_value ?? '' }}
                </span>
                <span v-else>—</span>
              </td>
              <td>{{ getStateValue(device, cap.key) }}</td>
              <td>{{ cap.tuya_dp_id ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else>No capabilities.</p>
        <hr />
      </div>
    </section>

    <!-- Action Test Endpoint -->
    <section>
      <h2>Test Action (POST /api/devices/{'{id}'}/action)</h2>
      <p>Send a command to a device to test connectivity and capability config.</p>

      <div>
        <label>
          Device ID:
          <select v-model="actionDeviceId">
            <option :value="null" disabled>Select a device</option>
            <option
              v-for="device in store.devices"
              :key="device.id"
              :value="device.id"
            >
              {{ device.name }} ({{ device.protocol }}, #{{ device.id }})
            </option>
          </select>
        </label>
      </div>

      <div>
        <label>
          Capability Key:
          <select v-model="actionCapabilityKey">
            <option value="" disabled>Select a capability</option>
            <template v-if="actionDeviceId !== null">
              <option
                v-for="cap in store.devices.find(d => d.id === actionDeviceId)?.capabilities.filter(c => c.capability_type === 'both' || c.capability_type === 'action') ?? []"
                :key="cap.key"
                :value="cap.key"
              >
                {{ cap.key }} ({{ cap.data_type }})
              </option>
            </template>
          </select>
        </label>
      </div>

      <div>
        <label>
          Value:
          <input v-model="actionValue" placeholder="true / false / 0 / 1 / on / off" />
        </label>
      </div>

      <button @click="sendAction" :disabled="actionDeviceId === null || !actionCapabilityKey">
        Send Action
      </button>

      <pre v-if="actionResult">{{ actionResult }}</pre>
      <p v-if="actionError" style="color: red;">Error: {{ actionError }}</p>
    </section>

    <!-- Read Raw DPS -->
    <section>
      <h2>Read Raw DPS (POST /api/devices/{'{id}'}/read)</h2>
      <p>Poll a Tuya device locally and show raw DP IDs and their current values. Use this to verify DP mappings.</p>

      <div>
        <label>
          Device:
          <select v-model="readDeviceId">
            <option :value="null" disabled>Select a device</option>
            <option
              v-for="device in store.devices.filter(d => d.protocol === 'tuya')"
              :key="device.id"
              :value="device.id"
            >
              {{ device.name }} (#{{ device.id }}, {{ device.ip_address || 'no IP' }})
            </option>
          </select>
        </label>
      </div>

      <button @click="readRawDps" :disabled="readDeviceId === null || reading">
        {{ reading ? 'Reading...' : 'Read DPS' }}
      </button>

      <div v-if="readResult">
        <table>
          <thead>
            <tr><th>DP ID</th><th>Value</th></tr>
          </thead>
          <tbody>
            <tr v-for="(val, dp) in readResult" :key="dp">
              <td>{{ dp }}</td>
              <td>{{ String(val) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="readError" style="color: red;">Error: {{ readError }}</p>
    </section>
  </div>
</template>
