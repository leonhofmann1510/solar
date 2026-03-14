<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useDevicesStore } from '@/stores/devices'
import AppShell from '@/components/layout/AppShell.vue'
import SectionHeader from '@/components/shared/SectionHeader.vue'
import EmptyState from '@/components/shared/EmptyState.vue'
import PendingDevicesBanner from '@/components/devices/PendingDevicesBanner.vue'
import DeviceModal from '@/components/devices/DeviceModal.vue'
import StatusDot from '@/components/shared/StatusDot.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Skeleton from 'primevue/skeleton'
import type { Device } from '@/types/device'

const store = useDevicesStore()

const selectedDevice = ref<Device | null>(null)
const deviceModalVisible = ref(false)

const discoveringMdns = ref(false)
const scanningTuya = ref(false)

// Pending confirm form
const confirmDialogVisible = ref(false)
const confirmingDevice = ref<Device | null>(null)
const confirmName = ref('')
const confirmRoom = ref('')
const confirmLoading = ref(false)

onMounted(async () => {
  await Promise.all([store.fetchAll(), store.fetchPending()])
})

function openDeviceModal(device: Device) {
  selectedDevice.value = device
  deviceModalVisible.value = true
}

function protocolSeverity(protocol: string) {
  switch (protocol) {
    case 'mqtt': return 'info'
    case 'tuya': return 'warn'
    case 'mdns': return 'secondary'
    default: return 'secondary'
  }
}

function deviceOnline(device: Device) {
  if (!device.last_seen_at) return false
  const age = Date.now() - new Date(device.last_seen_at).getTime()
  return age < 120_000
}

async function runDiscoverMdns() {
  discoveringMdns.value = true
  try {
    await store.discoverMdns()
  } finally {
    discoveringMdns.value = false
  }
}

async function runScanTuya() {
  scanningTuya.value = true
  try {
    await store.scanTuyaNetwork()
  } finally {
    scanningTuya.value = false
  }
}

function startConfirm(device: Device) {
  confirmingDevice.value = device
  confirmName.value = device.name
  confirmRoom.value = ''
  confirmDialogVisible.value = true
}

async function submitConfirm() {
  if (!confirmingDevice.value) return
  confirmLoading.value = true
  try {
    await store.confirm(confirmingDevice.value.id, {
      name: confirmName.value,
      room: confirmRoom.value || null,
    })
    confirmDialogVisible.value = false
  } finally {
    confirmLoading.value = false
  }
}

async function deletePending(id: number) {
  await store.remove(id)
}

function onDeviceUpdated() {
  store.fetchAll()
}
</script>

<template>
  <AppShell>
    <SectionHeader title="Devices">
      <template #actions>
        <Button
          icon="pi pi-search"
          label="Scan Network"
          size="small"
          outlined
          @click="runDiscoverMdns"
          :loading="discoveringMdns"
          class="hidden sm:inline-flex"
        />
        <Button
          icon="pi pi-wifi"
          label="Fetch Tuya"
          size="small"
          outlined
          @click="runScanTuya"
          :loading="scanningTuya"
          class="hidden sm:inline-flex"
        />
        <!-- Mobile: icon-only buttons -->
        <Button
          icon="pi pi-search"
          size="small"
          outlined
          @click="runDiscoverMdns"
          :loading="discoveringMdns"
          class="sm:hidden"
          aria-label="Scan Network"
        />
        <Button
          icon="pi pi-wifi"
          size="small"
          outlined
          @click="runScanTuya"
          :loading="scanningTuya"
          class="sm:hidden"
          aria-label="Fetch Tuya"
        />
      </template>
    </SectionHeader>

    <!-- Pending banner -->
    <div v-if="store.pending.length > 0" class="mb-4">
      <PendingDevicesBanner />
    </div>

    <!-- Pending devices table -->
    <div v-if="store.pending.length > 0" class="mb-6">
      <h3 class="text-sm font-medium text-sf-text-2 uppercase tracking-wider mb-3">Pending Confirmation</h3>
      <div class="bg-sf-surface rounded-sf shadow-sf overflow-hidden">
        <DataTable :value="store.pending" :rows="10" responsiveLayout="scroll" class="text-sm">
          <Column field="name" header="Name">
            <template #body="{ data }">
              <span class="font-medium text-sf-text-1">{{ data.name }}</span>
            </template>
          </Column>
          <Column field="protocol" header="Protocol" class="hidden md:table-cell">
            <template #body="{ data }">
              <Tag :value="data.protocol.toUpperCase()" :severity="protocolSeverity(data.protocol)" />
            </template>
          </Column>
          <Column field="raw_id" header="ID" class="hidden md:table-cell">
            <template #body="{ data }">
              <span class="text-xs text-sf-text-3 font-mono">{{ data.raw_id.substring(0, 20) }}{{ data.raw_id.length > 20 ? '...' : '' }}</span>
            </template>
          </Column>
          <Column header="Actions" style="width: 140px">
            <template #body="{ data }">
              <div class="flex gap-1">
                <Button label="Confirm" size="small" @click="startConfirm(data)" />
                <Button icon="pi pi-trash" size="small" severity="danger" text @click="deletePending(data.id)" aria-label="Delete" />
              </div>
            </template>
          </Column>
        </DataTable>
      </div>
    </div>

    <!-- Confirmed devices table -->
    <div class="bg-sf-surface rounded-sf shadow-sf overflow-hidden">
      <template v-if="store.loading">
        <div class="p-6 space-y-3">
          <Skeleton height="2rem" />
          <Skeleton height="2rem" />
          <Skeleton height="2rem" />
        </div>
      </template>
      <template v-else-if="store.devices.length === 0">
        <EmptyState
          icon="pi pi-objects-column"
          title="No devices yet"
          message="Scan your network or link your Tuya account to discover devices."
        />
      </template>
      <template v-else>
        <DataTable
          :value="store.devices"
          :rows="20"
          :paginator="store.devices.length > 20"
          responsiveLayout="scroll"
          class="text-sm"
          @row-click="(e: any) => openDeviceModal(e.data)"
          :rowHover="true"
          style="cursor: pointer"
        >
          <Column field="name" header="Name" :sortable="true">
            <template #body="{ data }">
              <span class="font-medium text-sf-text-1">{{ data.name }}</span>
            </template>
          </Column>
          <Column field="protocol" header="Protocol" :sortable="true" style="width: 100px">
            <template #body="{ data }">
              <Tag :value="data.protocol.toUpperCase()" :severity="protocolSeverity(data.protocol)" />
            </template>
          </Column>
          <Column header="Status" style="width: 100px">
            <template #body="{ data }">
              <StatusDot
                :color="deviceOnline(data) ? 'green' : 'red'"
                :label="deviceOnline(data) ? 'Online' : 'Offline'"
              />
            </template>
          </Column>
          <Column field="room" header="Room" :sortable="true" class="hidden md:table-cell">
            <template #body="{ data }">
              <span class="text-sf-text-2">{{ data.room || '\u2014' }}</span>
            </template>
          </Column>
          <Column header="" style="width: 50px" class="hidden md:table-cell">
            <template #body="{ data }">
              <Button icon="pi pi-pencil" text rounded size="small" @click.stop="openDeviceModal(data)" aria-label="Edit" />
            </template>
          </Column>
        </DataTable>
      </template>
    </div>

    <!-- Device detail modal -->
    <DeviceModal
      :device="selectedDevice"
      v-model:visible="deviceModalVisible"
      @updated="onDeviceUpdated"
    />

    <!-- Confirm dialog -->
    <Dialog
      v-model:visible="confirmDialogVisible"
      header="Confirm Device"
      :modal="true"
      :style="{ width: '90vw', maxWidth: '400px' }"
      :pt="{ root: { style: 'border-radius: 12px' } }"
    >
      <div class="space-y-4 py-2">
        <div>
          <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1">Name</label>
          <InputText v-model="confirmName" class="w-full text-sm" />
        </div>
        <div>
          <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1">Room (optional)</label>
          <InputText v-model="confirmRoom" class="w-full text-sm" placeholder="e.g. Kitchen" />
        </div>
        <div class="flex gap-2 pt-2">
          <Button label="Confirm" icon="pi pi-check" @click="submitConfirm" :loading="confirmLoading" />
          <Button label="Cancel" severity="secondary" text @click="confirmDialogVisible = false" />
        </div>
      </div>
    </Dialog>
  </AppShell>
</template>
