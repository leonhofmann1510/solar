<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { useTuyaSetup } from '@/composables/useTuyaSetup'
import { useMeterStore } from '@/stores/meter'
import QRCode from 'qrcode'

const meterStore = useMeterStore()
onMounted(() => meterStore.fetchStatus())

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{ 'update:visible': [value: boolean] }>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

// Settings sidebar sections
const sections = [
  { key: 'general', label: 'General', icon: 'pi pi-sliders-h' },
  { key: 'inverters', label: 'Inverters', icon: 'pi pi-server' },
  { key: 'mqtt', label: 'MQTT', icon: 'pi pi-share-alt' },
  { key: 'meter', label: 'Smart Meter', icon: 'pi pi-chart-line' },
  { key: 'tuya', label: 'Tuya Setup', icon: 'pi pi-qrcode' },
  { key: 'about', label: 'About', icon: 'pi pi-info-circle' },
] as const

type SectionKey = (typeof sections)[number]['key']
const activeSection = ref<SectionKey | null>(null)
const isMobile = ref(window.innerWidth < 768)

function onResize() {
  isMobile.value = window.innerWidth < 768
}

watch(dialogVisible, (v) => {
  if (v) {
    window.addEventListener('resize', onResize)
    activeSection.value = isMobile.value ? null : 'general'
  } else {
    window.removeEventListener('resize', onResize)
    activeSection.value = null
  }
})

function selectSection(key: SectionKey) {
  activeSection.value = key
}

function goBack() {
  activeSection.value = null
}

const activeSectionLabel = computed(() =>
  sections.find((s) => s.key === activeSection.value)?.label ?? 'Settings'
)

// --- Tuya Setup ---
const { qrUrl, status: tuyaStatus, devicesFound, errorMessage, startSetup, reset: resetTuya } = useTuyaSetup()
const userCode = ref('')
const qrDataUrl = ref<string | null>(null)

watch(qrUrl, async (url) => {
  if (url) {
    try {
      qrDataUrl.value = await QRCode.toDataURL(url, { width: 240, margin: 2 })
    } catch {
      qrDataUrl.value = null
    }
  } else {
    qrDataUrl.value = null
  }
})

async function handleTuyaStart() {
  if (!userCode.value.trim()) return
  await startSetup(userCode.value.trim())
}

function handleTuyaReset() {
  resetTuya()
  userCode.value = ''
  qrDataUrl.value = null
}
</script>

<template>
  <Dialog
    v-model:visible="dialogVisible"
    :modal="true"
    :closable="true"
    :header="isMobile && activeSection ? activeSectionLabel : 'Settings'"
    :style="isMobile ? { width: '100vw', height: '100vh', maxHeight: '100vh' } : { width: '900px', height: '600px' }"
    :breakpoints="{ '768px': '100vw' }"
    :pt="{
      root: { style: isMobile ? 'border-radius: 0' : 'border-radius: 12px; overflow: hidden' },
      content: { style: 'padding: 0; height: 100%; display: flex; flex-direction: column' },
      header: { style: 'padding: 1rem 1.25rem; border-bottom: 1px solid var(--sf-border)' },
    }"
  >
    <template v-if="isMobile && activeSection" #header>
      <div class="flex items-center gap-3 w-full">
        <button @click="goBack" class="p-1 -ml-1 text-sf-text-2 hover:text-sf-text-1">
          <i class="pi pi-arrow-left text-base" />
        </button>
        <span class="font-semibold text-sf-text-1">{{ activeSectionLabel }}</span>
      </div>
    </template>

    <div class="flex flex-1 overflow-hidden">
      <!-- Section list (sidebar on desktop, full page on mobile when no section) -->
      <div
        v-if="!isMobile || !activeSection"
        class="overflow-y-auto"
        :class="isMobile ? 'w-full' : 'w-[200px] border-r border-sf-border bg-slate-50'"
      >
        <nav class="py-2">
          <button
            v-for="section in sections"
            :key="section.key"
            @click="selectSection(section.key)"
            class="w-full flex items-center gap-3 px-4 py-3 text-sm font-medium text-left transition-colors"
            :class="activeSection === section.key && !isMobile
              ? 'bg-sf-green-50 text-sf-green-700'
              : 'text-sf-text-2 hover:bg-slate-100 hover:text-sf-text-1'"
          >
            <i :class="section.icon" class="text-base" />
            {{ section.label }}
            <i v-if="isMobile" class="pi pi-chevron-right ml-auto text-sf-text-3 text-xs" />
          </button>
        </nav>
      </div>

      <!-- Content panel (visible on desktop always, on mobile only when section selected) -->
      <div
        v-if="!isMobile || activeSection"
        class="flex-1 overflow-y-auto p-5"
      >
        <!-- General -->
        <div v-if="activeSection === 'general'" class="space-y-5">
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">App Name</label>
            <p class="text-sm text-sf-text-1">SolarFlow</p>
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">Poll Interval</label>
            <p class="text-sm text-sf-text-1">30 seconds</p>
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">Version</label>
            <p class="text-sm text-sf-text-1">1.0.0</p>
          </div>
        </div>

        <!-- Inverters -->
        <div v-if="activeSection === 'inverters'" class="space-y-5">
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">Inverter 1 (Hybrid)</label>
            <div class="flex items-center gap-2">
              <InputText modelValue="192.168.178.101" disabled class="flex-1 text-sm" />
              <Tag value="Unit 1" severity="info" />
            </div>
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">Inverter 2 (String)</label>
            <div class="flex items-center gap-2">
              <InputText modelValue="192.168.178.102" disabled class="flex-1 text-sm" />
              <Tag value="Unit 2" severity="info" />
            </div>
          </div>
          <p class="text-xs text-sf-text-3">Inverter addresses are configured via environment variables on the server.</p>
        </div>

        <!-- MQTT -->
        <div v-if="activeSection === 'mqtt'" class="space-y-5">
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">Broker Host</label>
            <InputText modelValue="localhost" disabled class="w-full text-sm" />
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">Port</label>
            <InputText modelValue="1883" disabled class="w-full text-sm" />
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">Username</label>
            <InputText modelValue="solarflow" disabled class="w-full text-sm" />
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">Password</label>
            <InputText modelValue="••••••••" disabled type="password" class="w-full text-sm" />
          </div>
          <p class="text-xs text-sf-text-3">MQTT settings are configured via environment variables on the server.</p>
        </div>

        <!-- Smart Meter -->
        <div v-if="activeSection === 'meter'" class="space-y-5">
          <div class="flex items-center justify-between">
            <div>
              <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1">Status</label>
              <p class="text-sm text-sf-text-1">Smart Meter monitoring</p>
            </div>
            <Tag
              :value="meterStore.status.enabled ? 'Enabled' : 'Disabled'"
              :severity="meterStore.status.enabled ? 'success' : 'secondary'"
            />
          </div>
          <div v-if="meterStore.status.enabled">
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">Device IP</label>
            <InputText :modelValue="meterStore.status.ip" disabled class="w-full text-sm" />
          </div>
          <p class="text-xs text-sf-text-3">
            Smart meter settings are configured via <code class="bg-slate-100 px-1 rounded">SMART_METER_ENABLED</code>
            and <code class="bg-slate-100 px-1 rounded">SMART_METER_IP</code> environment variables on the server.
          </p>
          <router-link v-if="meterStore.status.enabled" to="/meter" @click="dialogVisible = false">
            <Button label="Open Meter Page" icon="pi pi-chart-line" severity="secondary" class="w-full" />
          </router-link>
        </div>

        <!-- Tuya Setup -->
        <div v-if="activeSection === 'tuya'" class="space-y-5">
          <!-- Idle state: user code input -->
          <template v-if="tuyaStatus === 'idle'">
            <div>
              <h3 class="text-sm font-semibold text-sf-text-1 mb-2">Link your Tuya / Smart Life account</h3>
              <p class="text-xs text-sf-text-2 mb-4 leading-relaxed">
                Open the Smart Life app, go to <strong>Me &rarr; Settings &rarr; Account and Security &rarr; User Code</strong>
                and enter it below.
              </p>
            </div>
            <div>
              <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">User Code</label>
              <InputText
                v-model="userCode"
                placeholder="e.g. U7X9K2"
                class="w-full text-sm"
                @keyup.enter="handleTuyaStart"
              />
            </div>
            <Button
              label="Start Setup"
              icon="pi pi-qrcode"
              @click="handleTuyaStart"
              :disabled="!userCode.trim()"
              class="w-full"
            />
          </template>

          <!-- Pending state: QR code display -->
          <template v-else-if="tuyaStatus === 'pending'">
            <div class="text-center">
              <h3 class="text-sm font-semibold text-sf-text-1 mb-2">Scan this QR code</h3>
              <p class="text-xs text-sf-text-2 mb-4">
                Open the Smart Life app, tap <strong>+</strong> then <strong>Scan</strong>, and scan the code below.
              </p>
              <div v-if="qrDataUrl" class="inline-block bg-white p-3 rounded-sf shadow-sf">
                <img :src="qrDataUrl" alt="Tuya QR Code" class="w-48 h-48" />
              </div>
              <div v-else class="inline-flex items-center justify-center w-48 h-48 bg-slate-50 rounded-sf">
                <i class="pi pi-spin pi-spinner text-2xl text-sf-text-3" />
              </div>
              <div class="flex items-center justify-center gap-2 mt-4 text-sf-text-3">
                <i class="pi pi-spin pi-spinner text-sm" />
                <span class="text-xs">Waiting for scan...</span>
              </div>
              <Button
                label="Cancel"
                severity="secondary"
                text
                @click="handleTuyaReset"
                class="mt-3"
                size="small"
              />
            </div>
          </template>

          <!-- Success state -->
          <template v-else-if="tuyaStatus === 'success'">
            <div class="text-center py-4">
              <div class="w-16 h-16 rounded-full bg-sf-green-50 flex items-center justify-center mx-auto mb-4">
                <i class="pi pi-check text-2xl text-sf-green-600" />
              </div>
              <h3 class="text-base font-semibold text-sf-text-1 mb-1">Devices linked</h3>
              <p class="text-sm text-sf-text-2 mb-4">
                Found {{ devicesFound }} device{{ devicesFound === 1 ? '' : 's' }}.
                Go to Devices to confirm them.
              </p>
              <div class="flex gap-2 justify-center">
                <router-link to="/devices" @click="dialogVisible = false">
                  <Button label="Go to Devices" icon="pi pi-arrow-right" />
                </router-link>
                <Button label="Scan Again" severity="secondary" text @click="handleTuyaReset" />
              </div>
            </div>
          </template>

          <!-- Failed state -->
          <template v-else-if="tuyaStatus === 'failed'">
            <div class="text-center py-4">
              <div class="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-4">
                <i class="pi pi-times text-2xl text-sf-red-500" />
              </div>
              <h3 class="text-base font-semibold text-sf-text-1 mb-1">Setup failed</h3>
              <p class="text-sm text-sf-text-2 mb-4">{{ errorMessage || 'Something went wrong. Please try again.' }}</p>
              <Button label="Try Again" icon="pi pi-refresh" @click="handleTuyaReset" />
            </div>
          </template>
        </div>

        <!-- About -->
        <div v-if="activeSection === 'about'" class="space-y-5">
          <div>
            <h3 class="text-sm font-semibold text-sf-text-1 mb-2">SolarFlow</h3>
            <p class="text-xs text-sf-text-2 leading-relaxed">
              A self-hosted solar monitoring and smart home automation platform.
              Control your inverters, Tuya and MQTT devices, and build automation rules — all from one place.
            </p>
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">Version</label>
            <p class="text-sm text-sf-text-1">1.0.0</p>
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">Source</label>
            <p class="text-sm text-sf-green-600">github.com/solarflow</p>
          </div>
        </div>
      </div>
    </div>
  </Dialog>
</template>
