<script setup lang="ts">
import { ref, computed, watch, reactive } from 'vue'
import Dialog from 'primevue/dialog'
import TabView from 'primevue/tabview'
import TabPanel from 'primevue/tabpanel'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import InputSwitch from 'primevue/inputswitch'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import StatusDot from '@/components/shared/StatusDot.vue'
import { useDevicesStore } from '@/stores/devices'
import type { Device } from '@/types/device'

const props = defineProps<{
  device: Device | null
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  updated: []
}>()

const store = useDevicesStore()

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const editName = ref('')
const editRoom = ref('')
const editEnabled = ref(true)
const saving = ref(false)
const testing = ref<string | null>(null)
const testResult = ref<string | null>(null)
const testValues = reactive<Record<string, number | string>>({})

function getTestValue(capKey: string, dataType: string, minValue: number | null): number | string {
  if (testValues[capKey] !== undefined) return testValues[capKey]
  if (dataType === 'integer' || dataType === 'float') {
    return minValue ?? 0
  }
  return ''
}

function setTestValue(capKey: string, value: number | string) {
  testValues[capKey] = value
}

watch(() => props.device, (d) => {
  if (d) {
    editName.value = d.name
    editRoom.value = d.room || ''
    editEnabled.value = d.enabled
    testResult.value = null
  }
})

async function handleSave() {
  if (!props.device) return
  saving.value = true
  try {
    await store.update(props.device.id, {
      name: editName.value,
      room: editRoom.value || null,
      enabled: editEnabled.value,
    })
    emit('updated')
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  if (!props.device) return
  await store.remove(props.device.id)
  dialogVisible.value = false
}

async function handleTestAction(capKey: string, value: boolean | number | string) {
  if (!props.device) return
  testing.value = capKey
  testResult.value = null
  try {
    await store.sendAction(props.device.id, {
      capability_key: capKey,
      value,
    })
    testResult.value = `Sent ${capKey} = ${value}`
  } catch (e: any) {
    testResult.value = `Error: ${e.response?.data?.detail || e.message}`
  } finally {
    testing.value = null
  }
}

function getStateValue(capKey: string): string {
  const state = props.device?.states.find((s) => s.capability_key === capKey)
  if (!state) return '\u2014'
  if (state.value_boolean !== null) return String(state.value_boolean)
  if (state.value_numeric !== null) return String(state.value_numeric)
  if (state.value_string !== null) return state.value_string
  return '\u2014'
}

function getStateFreshness(capKey: string): 'green' | 'amber' | 'grey' {
  const state = props.device?.states.find((s) => s.capability_key === capKey)
  if (!state) return 'grey'
  const age = Date.now() - new Date(state.updated_at).getTime()
  if (age < 30_000) return 'green'
  return 'amber'
}

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 5) return 'just now'
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ago`
}

const protocolSeverity = computed(() => {
  switch (props.device?.protocol) {
    case 'mqtt': return 'info'
    case 'tuya': return 'warn'
    case 'mdns': return 'secondary'
    default: return 'secondary'
  }
})

const actionCapabilities = computed(() =>
  props.device?.capabilities.filter((c) => c.capability_type === 'action' || c.capability_type === 'both') ?? []
)
</script>

<template>
  <Dialog
    v-model:visible="dialogVisible"
    :modal="true"
    :header="device?.name || 'Device'"
    :style="{ width: '90vw', maxWidth: '520px' }"
    :pt="{ root: { style: 'border-radius: 12px; overflow: hidden' }, header: { style: 'border-bottom: 1px solid var(--sf-border)' } }"
  >
    <TabView v-if="device">
      <TabPanel value="info" header="Info">
        <div class="space-y-4 py-2">
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1">Name</label>
            <InputText v-model="editName" class="w-full text-sm" />
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1">Room</label>
            <InputText v-model="editRoom" class="w-full text-sm" placeholder="e.g. Kitchen" />
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1">Protocol</label>
            <Tag :value="device.protocol.toUpperCase()" :severity="protocolSeverity" />
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1">Raw ID</label>
            <p class="text-xs text-sf-text-3 font-mono break-all">{{ device.raw_id }}</p>
          </div>
          <div v-if="device.ip_address">
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1">IP Address</label>
            <p class="text-sm text-sf-text-1">{{ device.ip_address }}</p>
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1">First Seen</label>
            <p class="text-sm text-sf-text-1">{{ new Date(device.first_seen_at).toLocaleDateString() }}</p>
          </div>

          <div class="flex items-center gap-3 pt-2">
            <Button label="Save" icon="pi pi-check" @click="handleSave" :loading="saving" size="small" />
            <Button label="Delete" icon="pi pi-trash" severity="danger" text @click="handleDelete" size="small" />
          </div>
        </div>
      </TabPanel>

      <TabPanel value="state" header="State">
        <div class="py-2">
          <table v-if="device.capabilities.length > 0" class="w-full text-sm">
            <thead>
              <tr class="border-b border-sf-border">
                <th class="text-left py-2 text-xs font-medium text-sf-text-2 uppercase tracking-wider">Capability</th>
                <th class="text-left py-2 text-xs font-medium text-sf-text-2 uppercase tracking-wider">Value</th>
                <th class="text-left py-2 text-xs font-medium text-sf-text-2 uppercase tracking-wider">Updated</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="cap in device.capabilities" :key="cap.key" class="border-b border-sf-border last:border-0">
                <td class="py-2.5">
                  <div class="flex items-center gap-2">
                    <StatusDot :color="getStateFreshness(cap.key)" />
                    <span class="text-sf-text-1">{{ cap.display_name || cap.key }}</span>
                  </div>
                </td>
                <td class="py-2.5">
                  <span class="font-mono text-sf-text-1">{{ getStateValue(cap.key) }}</span>
                  <span v-if="cap.unit" class="text-sf-text-3 ml-1">{{ cap.unit }}</span>
                </td>
                <td class="py-2.5 text-xs text-sf-text-3">
                  {{ device.states.find(s => s.capability_key === cap.key)?.updated_at
                    ? timeAgo(device.states.find(s => s.capability_key === cap.key)!.updated_at)
                    : '\u2014' }}
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="text-sm text-sf-text-3 py-4 text-center">No capabilities found.</p>
        </div>
      </TabPanel>

      <TabPanel value="settings" header="Settings">
        <div class="space-y-4 py-2">
          <div class="flex items-center justify-between">
            <label class="text-sm font-medium text-sf-text-1">Enabled</label>
            <InputSwitch v-model="editEnabled" @change="handleSave" />
          </div>

          <template v-if="actionCapabilities.length > 0">
            <div class="border-t border-sf-border pt-4">
              <p class="text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-3">Test Actions</p>
              <div v-for="cap in actionCapabilities" :key="cap.key" class="flex items-center gap-2 mb-3">
                <span class="text-sm text-sf-text-1 flex-1">{{ cap.display_name || cap.key }}</span>
                
                <!-- Boolean: On/Off buttons -->
                <template v-if="cap.data_type === 'boolean'">
                  <Button
                    label="On"
                    size="small"
                    severity="success"
                    outlined
                    @click="handleTestAction(cap.key, true)"
                    :loading="testing === cap.key"
                  />
                  <Button
                    label="Off"
                    size="small"
                    severity="secondary"
                    outlined
                    @click="handleTestAction(cap.key, false)"
                    :loading="testing === cap.key"
                  />
                </template>
                
                <!-- Integer/Float: Number input with send button -->
                <template v-else-if="cap.data_type === 'integer' || cap.data_type === 'float'">
                  <InputNumber
                    :modelValue="getTestValue(cap.key, cap.data_type, cap.min_value) as number"
                    @update:modelValue="setTestValue(cap.key, $event ?? 0)"
                    :min="cap.min_value ?? undefined"
                    :max="cap.max_value ?? undefined"
                    :minFractionDigits="cap.data_type === 'float' ? 1 : 0"
                    :maxFractionDigits="cap.data_type === 'float' ? 2 : 0"
                    showButtons
                    buttonLayout="horizontal"
                    :step="cap.data_type === 'float' ? 0.5 : 1"
                    class="w-28"
                    size="small"
                    :pt="{ input: { class: 'text-center text-sm w-12' } }"
                  />
                  <span v-if="cap.unit" class="text-xs text-sf-text-3">{{ cap.unit }}</span>
                  <Button
                    label="Send"
                    size="small"
                    severity="primary"
                    outlined
                    @click="handleTestAction(cap.key, getTestValue(cap.key, cap.data_type, cap.min_value))"
                    :loading="testing === cap.key"
                  />
                </template>
                
                <!-- String: Text input with send button -->
                <template v-else>
                  <InputText
                    :modelValue="getTestValue(cap.key, cap.data_type, null) as string"
                    @update:modelValue="setTestValue(cap.key, $event)"
                    placeholder="Value"
                    class="w-24 text-sm"
                  />
                  <Button
                    label="Send"
                    size="small"
                    severity="primary"
                    outlined
                    @click="handleTestAction(cap.key, getTestValue(cap.key, cap.data_type, null))"
                    :loading="testing === cap.key"
                  />
                </template>
              </div>
            </div>
          </template>

          <p v-if="testResult" class="text-xs text-sf-text-2 bg-slate-50 rounded-sf-sm p-2 mt-2">
            {{ testResult }}
          </p>
        </div>
      </TabPanel>
    </TabView>
  </Dialog>
</template>
