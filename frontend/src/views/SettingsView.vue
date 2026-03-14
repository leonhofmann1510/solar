<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import QRCode from 'qrcode'
import { useTuyaSetup } from '@/composables/useTuyaSetup'
import { useDevicesStore } from '@/stores/devices'

const router = useRouter()
const devicesStore = useDevicesStore()
const { qrUrl, status, devicesFound, errorMessage, startSetup, reset } = useTuyaSetup()

const userCode = ref('')
const qrDataUrl = ref<string | null>(null)

async function handleStart() {
  const code = userCode.value.trim()
  if (!code) return
  await startSetup(code)
}

function handleTryAgain() {
  reset()
  userCode.value = ''
}

async function goToDevices() {
  await devicesStore.fetchPending()
  router.push('/devices')
}

// Render QR image whenever qrUrl changes
watch(qrUrl, async (url) => {
  if (url) {
    qrDataUrl.value = await QRCode.toDataURL(url, { width: 280, margin: 2 })
  } else {
    qrDataUrl.value = null
  }
})
</script>

<template>
  <div>
    <h1>Settings</h1>

    <section>
      <h2>Tuya Device Setup</h2>
      <p>
        Link your Tuya/Smart Life devices without a developer account.
        This uses the Smart Life app's QR code login.
      </p>

      <!-- Step 1: User Code input -->
      <div v-if="status === 'idle'">
        <div style="margin-bottom: 12px;">
          <label>
            <strong>User Code</strong>
            <br />
            <input
              v-model="userCode"
              placeholder="Enter your User Code"
              style="width: 280px; padding: 6px 8px; margin-top: 4px;"
            />
          </label>
        </div>
        <p style="color: #666; font-size: 0.9em; margin-bottom: 12px;">
          Find it in the Smart Life app: <strong>Me → Settings → Account and Security → User Code</strong>
        </p>
        <button @click="handleStart" :disabled="!userCode.trim()">
          Start Setup
        </button>
      </div>

      <!-- Step 2: QR Code display + linking progress -->
      <div v-else-if="status === 'pending'">
        <div v-if="qrDataUrl" style="margin-bottom: 16px;">
          <img :src="qrDataUrl" alt="Tuya QR Code" style="border: 1px solid #ddd; border-radius: 4px;" />
        </div>
        <p v-else>Generating QR code...</p>
        <p>
          <strong>Open the Smart Life app → tap + → Scan</strong> and scan this QR code.
        </p>
        <p style="color: #666; font-size: 0.9em;">
          After scanning, this page will update automatically while devices are being linked and IPs are refreshed.
        </p>
        <button @click="handleTryAgain">Cancel</button>
      </div>

      <!-- Step 3: Success -->
      <div v-else-if="status === 'success'">
        <p style="color: green;">
          <strong v-if="devicesFound > 0">Found {{ devicesFound }} new device(s).</strong>
          <strong v-else>All devices already linked.</strong>
        </p>
        <p v-if="devicesFound > 0">
          Go to <strong>Devices</strong> to confirm and name them.
        </p>
        <p v-else>
          Local keys and IP addresses have been refreshed. Your devices are ready to use.
        </p>
        <button @click="goToDevices" style="margin-right: 8px;">Go to Devices</button>
        <button @click="handleTryAgain">Run Again</button>
      </div>

      <!-- Step 4: Failure -->
      <div v-else-if="status === 'failed'">
        <p style="color: red;">
          <strong>Setup failed.</strong> {{ errorMessage }}
        </p>
        <button @click="handleTryAgain">Try Again</button>
      </div>
    </section>
  </div>
</template>
