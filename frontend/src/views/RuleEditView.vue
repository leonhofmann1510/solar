<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRulesStore } from '@/stores/rules'
import { useDevicesStore } from '@/stores/devices'
import { rulesApi } from '@/api/rules'
import AppShell from '@/components/layout/AppShell.vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import type { Operator, ConditionLogic, OnClearAction } from '@/types/rule'

const route = useRoute()
const router = useRouter()
const rulesStore = useRulesStore()
const devicesStore = useDevicesStore()

const isNew = computed(() => route.path === '/rules/new')
const ruleId = computed(() => isNew.value ? null : Number(route.params.id))

const activeStep = ref(0)
const saving = ref(false)
const loading = ref(false)

// Form state
const ruleName = ref('')
const conditionLogic = ref<ConditionLogic>('AND')
const cooldownSeconds = ref(300)
const onClearAction = ref<OnClearAction>('none')
const conditions = ref<{ field: string; operator: Operator; value: number }[]>([])
const actions = ref<{ mqtt_topic: string; mqtt_payload: string }[]>([])

const steps = ['Name & Logic', 'Conditions', 'Actions', 'Review']

const operatorOptions = [
  { label: '>', value: 'gt' },
  { label: '<', value: 'lt' },
  { label: '\u2265', value: 'gte' },
  { label: '\u2264', value: 'lte' },
  { label: '=', value: 'eq' },
  { label: '\u2260', value: 'neq' },
]

const onClearOptions = [
  { label: 'None', value: 'none' },
  { label: 'Reverse', value: 'reverse' },
  { label: 'Custom', value: 'custom' },
]

// Inverter fields for conditions
const inverterFields = [
  'pv_power_w',
  'battery_soc_pct',
  'battery_power_w',
  'grid_power_w',
  'house_load_w',
  'pv_yield_today_kwh',
  'feed_in_today_kwh',
  'grid_buy_today_kwh',
  'inverter_temp_c',
  'grid_frequency_hz',
]

const fieldOptions = computed(() =>
  inverterFields.map((f) => ({ label: f, value: f }))
)

onMounted(async () => {
  await devicesStore.fetchAll()

  if (!isNew.value && ruleId.value) {
    loading.value = true
    try {
      const rule = await rulesApi.getOne(ruleId.value)
      ruleName.value = rule.name
      conditionLogic.value = rule.condition_logic
      cooldownSeconds.value = rule.cooldown_seconds
      onClearAction.value = rule.on_clear_action
      conditions.value = [...rule.conditions]
      actions.value = [...rule.actions]
    } finally {
      loading.value = false
    }
  }
})

function addCondition() {
  conditions.value.push({ field: 'pv_power_w', operator: 'gt', value: 0 })
}

function removeCondition(idx: number) {
  conditions.value.splice(idx, 1)
}

function addAction() {
  actions.value.push({ mqtt_topic: '', mqtt_payload: '' })
}

function removeAction(idx: number) {
  actions.value.splice(idx, 1)
}

function nextStep() {
  if (activeStep.value < steps.length - 1) activeStep.value++
}

function prevStep() {
  if (activeStep.value > 0) activeStep.value--
}

function operatorLabel(op: Operator): string {
  return operatorOptions.find((o) => o.value === op)?.label ?? op
}

async function handleSave() {
  saving.value = true
  try {
    const payload = {
      name: ruleName.value,
      enabled: true,
      condition_logic: conditionLogic.value,
      conditions: conditions.value,
      actions: actions.value,
      on_clear_action: onClearAction.value,
      on_clear_payload: null,
      cooldown_seconds: cooldownSeconds.value,
    }

    if (isNew.value) {
      await rulesStore.create(payload)
    } else if (ruleId.value) {
      await rulesStore.update(ruleId.value, payload)
    }
    router.push('/rules')
  } finally {
    saving.value = false
  }
}

const canProceedStep0 = computed(() => ruleName.value.trim().length > 0)
const canProceedStep1 = computed(() => conditions.value.length > 0)
const canProceedStep2 = computed(() => actions.value.length > 0 && actions.value.every((a) => a.mqtt_topic.trim()))
</script>

<template>
  <AppShell>
    <div class="max-w-2xl mx-auto">
      <!-- Header -->
      <div class="flex items-center gap-3 mb-6">
        <Button icon="pi pi-arrow-left" text rounded @click="router.push('/rules')" aria-label="Back" />
        <h1 class="text-lg font-semibold text-sf-text-1">
          {{ isNew ? 'Create Rule' : 'Edit Rule' }}
        </h1>
      </div>

      <!-- Step indicator -->
      <div class="flex items-center gap-1 mb-6 overflow-x-auto">
        <template v-for="(step, idx) in steps" :key="idx">
          <button
            @click="activeStep = idx"
            class="flex items-center gap-2 px-3 py-2 rounded-sf-sm text-sm font-medium whitespace-nowrap transition-colors"
            :class="idx === activeStep
              ? 'bg-sf-green-50 text-sf-green-700'
              : idx < activeStep
                ? 'text-sf-green-600'
                : 'text-sf-text-3'"
          >
            <span
              class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold"
              :class="idx === activeStep
                ? 'bg-sf-green-500 text-white'
                : idx < activeStep
                  ? 'bg-sf-green-100 text-sf-green-700'
                  : 'bg-slate-100 text-sf-text-3'"
            >{{ idx + 1 }}</span>
            <span class="hidden sm:inline">{{ step }}</span>
          </button>
          <i v-if="idx < steps.length - 1" class="pi pi-chevron-right text-sf-text-3 text-xs mx-1" />
        </template>
      </div>

      <div class="bg-sf-surface rounded-sf shadow-sf p-5">
        <!-- Step 1: Name & Logic -->
        <div v-if="activeStep === 0" class="space-y-5">
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">Rule Name</label>
            <InputText v-model="ruleName" class="w-full" placeholder="e.g. Battery full — turn on washer" />
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">Condition Logic</label>
            <div class="flex gap-2">
              <button
                @click="conditionLogic = 'AND'"
                class="px-4 py-2 rounded-sf-sm text-sm font-medium transition-colors"
                :class="conditionLogic === 'AND' ? 'bg-sf-green-500 text-white' : 'bg-slate-100 text-sf-text-2'"
              >AND</button>
              <button
                @click="conditionLogic = 'OR'"
                class="px-4 py-2 rounded-sf-sm text-sm font-medium transition-colors"
                :class="conditionLogic === 'OR' ? 'bg-sf-green-500 text-white' : 'bg-slate-100 text-sf-text-2'"
              >OR</button>
            </div>
            <p class="text-xs text-sf-text-3 mt-1">
              {{ conditionLogic === 'AND' ? 'All conditions must match' : 'Any condition can match' }}
            </p>
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">Cooldown (seconds)</label>
            <InputNumber v-model="cooldownSeconds" :min="0" :max="86400" class="w-full" />
          </div>
          <div>
            <label class="block text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1.5">On Condition Clear</label>
            <Select v-model="onClearAction" :options="onClearOptions" optionLabel="label" optionValue="value" class="w-full" />
          </div>
        </div>

        <!-- Step 2: Conditions -->
        <div v-else-if="activeStep === 1" class="space-y-4">
          <p class="text-xs font-medium text-sf-text-2 uppercase tracking-wider">
            Conditions ({{ conditionLogic }})
          </p>

          <div
            v-for="(cond, idx) in conditions"
            :key="idx"
            class="flex items-end gap-2 p-3 bg-slate-50 rounded-sf-sm"
          >
            <div class="flex-1 min-w-0">
              <label class="block text-[10px] text-sf-text-3 mb-0.5">Field</label>
              <Select v-model="cond.field" :options="fieldOptions" optionLabel="label" optionValue="value" class="w-full text-sm" />
            </div>
            <div class="w-20">
              <label class="block text-[10px] text-sf-text-3 mb-0.5">Op</label>
              <Select v-model="cond.operator" :options="operatorOptions" optionLabel="label" optionValue="value" class="w-full text-sm" />
            </div>
            <div class="w-24">
              <label class="block text-[10px] text-sf-text-3 mb-0.5">Value</label>
              <InputNumber v-model="cond.value" class="w-full text-sm" />
            </div>
            <Button icon="pi pi-times" text rounded severity="danger" size="small" @click="removeCondition(idx)" aria-label="Remove" />
          </div>

          <Button label="Add Condition" icon="pi pi-plus" text size="small" @click="addCondition" />
        </div>

        <!-- Step 3: Actions -->
        <div v-else-if="activeStep === 2" class="space-y-4">
          <p class="text-xs font-medium text-sf-text-2 uppercase tracking-wider">Actions</p>

          <div
            v-for="(action, idx) in actions"
            :key="idx"
            class="flex items-end gap-2 p-3 bg-slate-50 rounded-sf-sm"
          >
            <div class="flex-1 min-w-0">
              <label class="block text-[10px] text-sf-text-3 mb-0.5">MQTT Topic</label>
              <InputText v-model="action.mqtt_topic" class="w-full text-sm" placeholder="e.g. shellies/shelly1/relay/0/command" />
            </div>
            <div class="flex-1 min-w-0">
              <label class="block text-[10px] text-sf-text-3 mb-0.5">Payload</label>
              <InputText v-model="action.mqtt_payload" class="w-full text-sm" placeholder="e.g. on" />
            </div>
            <Button icon="pi pi-times" text rounded severity="danger" size="small" @click="removeAction(idx)" aria-label="Remove" />
          </div>

          <Button label="Add Action" icon="pi pi-plus" text size="small" @click="addAction" />
        </div>

        <!-- Step 4: Review -->
        <div v-else-if="activeStep === 3" class="space-y-5">
          <div>
            <p class="text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1">Rule Name</p>
            <p class="text-base font-semibold text-sf-text-1">{{ ruleName }}</p>
          </div>

          <div>
            <p class="text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1">Logic</p>
            <p class="text-sm text-sf-text-1">
              {{ conditionLogic === 'AND' ? 'ALL conditions must match' : 'ANY condition can match' }}
            </p>
          </div>

          <div>
            <p class="text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1">Cooldown</p>
            <p class="text-sm text-sf-text-1">{{ Math.floor(cooldownSeconds / 60) }} minutes</p>
          </div>

          <div>
            <p class="text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-2">Conditions</p>
            <div v-for="(cond, idx) in conditions" :key="idx" class="flex items-center gap-2 text-sm text-sf-text-1 mb-1">
              <i class="pi pi-check text-sf-green-500 text-xs" />
              <span>{{ cond.field }} {{ operatorLabel(cond.operator) }} {{ cond.value }}</span>
            </div>
          </div>

          <div>
            <p class="text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-2">Actions</p>
            <div v-for="(action, idx) in actions" :key="idx" class="flex items-center gap-2 text-sm text-sf-text-1 mb-1">
              <i class="pi pi-arrow-right text-sf-green-500 text-xs" />
              <span class="font-mono text-xs">{{ action.mqtt_topic }}</span>
              <span class="text-sf-text-3">=</span>
              <span class="font-mono text-xs">{{ action.mqtt_payload }}</span>
            </div>
          </div>

          <div>
            <p class="text-xs font-medium text-sf-text-2 uppercase tracking-wider mb-1">On Clear</p>
            <p class="text-sm text-sf-text-1 capitalize">{{ onClearAction }}</p>
          </div>
        </div>

        <!-- Navigation -->
        <div class="flex items-center justify-between mt-6 pt-4 border-t border-sf-border">
          <Button
            v-if="activeStep > 0"
            label="Back"
            icon="pi pi-arrow-left"
            severity="secondary"
            text
            @click="prevStep"
          />
          <span v-else />

          <Button
            v-if="activeStep < steps.length - 1"
            label="Next"
            icon="pi pi-arrow-right"
            iconPos="right"
            @click="nextStep"
            :disabled="
              (activeStep === 0 && !canProceedStep0) ||
              (activeStep === 1 && !canProceedStep1) ||
              (activeStep === 2 && !canProceedStep2)
            "
          />
          <Button
            v-else
            label="Save Rule"
            icon="pi pi-check"
            @click="handleSave"
            :loading="saving"
          />
        </div>
      </div>
    </div>
  </AppShell>
</template>
