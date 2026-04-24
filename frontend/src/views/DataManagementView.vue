<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useConfirm } from 'primevue/useconfirm'
import AppShell from '@/components/layout/AppShell.vue'
import { useDataStore } from '@/stores/data'
import type { EVSessionRecord, EVSessionUpdate, InverterDailyStat, InverterDailyStatUpdate, MeterReadingRecord, MeterReadingUpdate } from '@/types/data'
import Button from 'primevue/button'
import Column from 'primevue/column'
import ConfirmDialog from 'primevue/confirmdialog'
import DataTable from 'primevue/datatable'
import DatePicker from 'primevue/datepicker'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import Message from 'primevue/message'

type DataTab = 'inverter' | 'meter' | 'ev'

const store = useDataStore()
const confirm = useConfirm()

const activeTab = ref<DataTab>('inverter')
const dateRange = ref<[Date, Date] | null>(null)

const tabs: { value: DataTab; label: string }[] = [
  { value: 'inverter', label: 'Inverter Stats' },
  { value: 'meter', label: 'Meter Readings' },
  { value: 'ev', label: 'EV Sessions' },
]

function countFor(tab: DataTab): number {
  if (tab === 'inverter') return store.counts.inverter_stats
  if (tab === 'meter') return store.counts.meter_readings
  return store.counts.ev_sessions
}

// ── Edit dialogs ───────────────────────────────────────────────────────────────

const editInverterVisible = ref(false)
const editInverterDraft = ref<InverterDailyStatUpdate & { id: number; timestamp: string; inverter_id: string }>({
  id: 0,
  timestamp: '',
  inverter_id: '',
  pv_yield_today_kwh: 0,
  feed_in_today_kwh: null,
  grid_buy_today_kwh: null,
})

const editMeterVisible = ref(false)
const editMeterDraft = ref<MeterReadingUpdate & { id: number; timestamp: string }>({
  id: 0,
  timestamp: '',
  consumption_kwh: 0,
  feed_in_kwh: 0,
})

const editEVVisible = ref(false)
const editEVDraft = ref<{
  id: number
  startedAt: Date | null
  endedAt: Date | null
  kwh_total: number
  kwh_solar: number
  kwh_grid: number
  charging_power_kw: number
  cost_eur: number
  savings_vs_gas_eur: number
}>({
  id: 0,
  startedAt: null,
  endedAt: null,
  kwh_total: 0,
  kwh_solar: 0,
  kwh_grid: 0,
  charging_power_kw: 0,
  cost_eur: 0,
  savings_vs_gas_eur: 0,
})

// ── Init ───────────────────────────────────────────────────────────────────────

onMounted(async () => {
  await Promise.all([store.fetchInverterStats(), store.fetchCounts()])
})

// ── Tab lazy loading ───────────────────────────────────────────────────────────

watch(activeTab, (tab) => {
  if (tab === 'meter' && !store.meterLoaded) store.fetchMeterReadings()
  if (tab === 'ev' && !store.evLoaded) store.fetchEVSessions()
})

// ── Filter ─────────────────────────────────────────────────────────────────────

async function applyFilter() {
  if (dateRange.value) {
    store.filter.dateFrom = dateRange.value[0]
    store.filter.dateTo = dateRange.value[1]
  } else {
    store.filter.dateFrom = null
    store.filter.dateTo = null
  }
  store.meterLoaded = false
  store.evLoaded = false
  await Promise.all([
    store.fetchInverterStats(),
    store.fetchCounts(),
  ])
  if (activeTab.value === 'meter') store.fetchMeterReadings()
  if (activeTab.value === 'ev') store.fetchEVSessions()
}

function resetFilter() {
  dateRange.value = null
  applyFilter()
}

// ── Formatters ─────────────────────────────────────────────────────────────────

function fmtTs(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function fmtNum(v: number | null | undefined, dec = 2) {
  if (v == null) return '—'
  return v.toFixed(dec)
}

// ── Inverter edit/delete ────────────────────────────────────────────────────────

function openEditInverter(row: InverterDailyStat) {
  editInverterDraft.value = {
    id: row.id,
    timestamp: row.timestamp,
    inverter_id: row.inverter_id,
    pv_yield_today_kwh: row.pv_yield_today_kwh,
    feed_in_today_kwh: row.feed_in_today_kwh,
    grid_buy_today_kwh: row.grid_buy_today_kwh,
  }
  editInverterVisible.value = true
}

async function saveInverter() {
  const { id, timestamp, inverter_id, ...body } = editInverterDraft.value
  await store.updateInverterStat(id, body)
  editInverterVisible.value = false
}

function confirmDeleteInverter(id: number) {
  confirm.require({
    message: 'Delete this inverter stat record? This cannot be undone.',
    header: 'Delete Record',
    icon: 'pi pi-trash',
    rejectLabel: 'Cancel',
    acceptLabel: 'Delete',
    acceptClass: 'p-button-danger',
    accept: () => store.deleteInverterStatRecord(id),
  })
}

// ── Meter edit/delete ──────────────────────────────────────────────────────────

function openEditMeter(row: MeterReadingRecord) {
  editMeterDraft.value = {
    id: row.id,
    timestamp: row.timestamp,
    consumption_kwh: row.consumption_kwh,
    feed_in_kwh: row.feed_in_kwh,
  }
  editMeterVisible.value = true
}

async function saveMeter() {
  const { id, timestamp, ...body } = editMeterDraft.value
  await store.updateMeterReading(id, body)
  editMeterVisible.value = false
}

function confirmDeleteMeter(id: number) {
  confirm.require({
    message: 'Delete this meter reading? This cannot be undone.',
    header: 'Delete Record',
    icon: 'pi pi-trash',
    rejectLabel: 'Cancel',
    acceptLabel: 'Delete',
    acceptClass: 'p-button-danger',
    accept: () => store.deleteMeterReadingRecord(id),
  })
}

// ── EV edit/delete ─────────────────────────────────────────────────────────────

function openEditEV(row: EVSessionRecord) {
  editEVDraft.value = {
    id: row.id,
    startedAt: new Date(row.started_at),
    endedAt: row.ended_at ? new Date(row.ended_at) : null,
    kwh_total: row.kwh_total,
    kwh_solar: row.kwh_solar,
    kwh_grid: row.kwh_grid,
    charging_power_kw: row.charging_power_kw,
    cost_eur: row.cost_eur,
    savings_vs_gas_eur: row.savings_vs_gas_eur,
  }
  editEVVisible.value = true
}

async function saveEV() {
  const { id, startedAt, endedAt, ...rest } = editEVDraft.value
  await store.updateEVSession(id, {
    ...rest,
    started_at: startedAt ? startedAt.toISOString() : undefined,
    ended_at: endedAt ? endedAt.toISOString() : undefined,
  })
  editEVVisible.value = false
}

function confirmDeleteEV(id: number) {
  confirm.require({
    message: 'Delete this EV session? This cannot be undone.',
    header: 'Delete Record',
    icon: 'pi pi-trash',
    rejectLabel: 'Cancel',
    acceptLabel: 'Delete',
    acceptClass: 'p-button-danger',
    accept: () => store.deleteEVSessionRecord(id),
  })
}
</script>

<template>
  <AppShell>
    <!-- Page header -->
    <div class="mb-6">
      <h1 class="text-xl font-semibold text-sf-text-1">Data Management</h1>
      <p class="text-sm text-sf-text-2 mt-0.5">Inspect and correct inverter stats, meter readings, and EV sessions</p>
    </div>

    <!-- Filter bar -->
    <div class="bg-sf-surface rounded-sf shadow-sf p-4 mb-4 flex flex-wrap gap-3 items-end">
      <div class="flex flex-col gap-1 flex-1 min-w-[200px]">
        <span class="text-xs font-medium text-sf-text-3 uppercase tracking-wide">Date range</span>
        <DatePicker
          v-model="dateRange"
          selectionMode="range"
          :manualInput="false"
          placeholder="All time"
          dateFormat="dd.mm.yy"
          showButtonBar
          fluid
        />
      </div>
      <div class="flex gap-2">
        <Button label="Apply" icon="pi pi-filter" @click="applyFilter" />
        <Button label="Reset" severity="secondary" icon="pi pi-times" @click="resetFilter" />
      </div>
    </div>

    <!-- Tab switcher -->
    <div class="flex items-center justify-between mb-3">
      <div class="flex gap-1 bg-slate-100 rounded-sf p-1">
        <button
          v-for="tab in tabs"
          :key="tab.value"
          @click="activeTab = tab.value"
          class="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded transition-colors"
          :class="activeTab === tab.value
            ? 'bg-sf-surface text-sf-text-1 shadow-sm'
            : 'text-sf-text-3 hover:text-sf-text-2'"
        >
          {{ tab.label }}
          <span
            v-if="countFor(tab.value) > 0"
            class="text-xs rounded-full px-1.5 py-0.5 leading-none font-medium tabular-nums"
            :class="activeTab === tab.value
              ? 'bg-sf-green-100 text-sf-green-700'
              : 'bg-slate-200 text-slate-500'"
          >{{ countFor(tab.value) }}</span>
        </button>
      </div>
    </div>

    <!-- Inverter Stats -->
    <div v-show="activeTab === 'inverter'" class="bg-sf-surface rounded-sf shadow-sf overflow-hidden">
      <DataTable
        :value="store.inverterStats"
        :loading="store.loadingInverter"
        :rows="100"
        responsiveLayout="scroll"
        class="text-sm"
        :rowHover="true"
      >
        <Column field="timestamp" header="Timestamp" style="min-width: 160px">
          <template #body="{ data }">{{ fmtTs(data.timestamp) }}</template>
        </Column>
        <Column field="inverter_id" header="Inverter" style="width: 110px" class="hidden md:table-cell" />
        <Column field="date" header="Date" style="width: 110px" class="hidden md:table-cell" />
        <Column field="hour" header="Hour" style="width: 70px" class="hidden md:table-cell" />
        <Column field="pv_yield_today_kwh" header="PV Yield (kWh)" style="width: 130px">
          <template #body="{ data }">{{ fmtNum(data.pv_yield_today_kwh) }}</template>
        </Column>
        <Column field="feed_in_today_kwh" header="Feed-in (kWh)" style="width: 130px" class="hidden md:table-cell">
          <template #body="{ data }">{{ fmtNum(data.feed_in_today_kwh) }}</template>
        </Column>
        <Column field="grid_buy_today_kwh" header="Grid Buy (kWh)" style="width: 130px" class="hidden md:table-cell">
          <template #body="{ data }">{{ fmtNum(data.grid_buy_today_kwh) }}</template>
        </Column>
        <Column header="" style="width: 80px" frozen alignFrozen="right">
          <template #body="{ data }">
            <div class="flex gap-1">
              <Button icon="pi pi-pencil" text rounded size="small" @click="openEditInverter(data)" aria-label="Edit" />
              <Button icon="pi pi-trash" text rounded size="small" severity="danger" @click="confirmDeleteInverter(data.id)" aria-label="Delete" />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <!-- Meter Readings -->
    <div v-show="activeTab === 'meter'" class="bg-sf-surface rounded-sf shadow-sf overflow-hidden">
      <DataTable
        :value="store.meterReadings"
        :loading="store.loadingMeter"
        :rows="100"
        responsiveLayout="scroll"
        class="text-sm"
        :rowHover="true"
      >
        <Column field="timestamp" header="Timestamp" style="min-width: 160px">
          <template #body="{ data }">{{ fmtTs(data.timestamp) }}</template>
        </Column>
        <Column field="consumption_kwh" header="Consumption (kWh)" style="width: 170px">
          <template #body="{ data }">{{ fmtNum(data.consumption_kwh, 4) }}</template>
        </Column>
        <Column field="feed_in_kwh" header="Feed-in (kWh)" style="width: 150px">
          <template #body="{ data }">{{ fmtNum(data.feed_in_kwh, 4) }}</template>
        </Column>
        <Column header="" style="width: 80px" frozen alignFrozen="right">
          <template #body="{ data }">
            <div class="flex gap-1">
              <Button icon="pi pi-pencil" text rounded size="small" @click="openEditMeter(data)" aria-label="Edit" />
              <Button icon="pi pi-trash" text rounded size="small" severity="danger" @click="confirmDeleteMeter(data.id)" aria-label="Delete" />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <!-- EV Sessions -->
    <div v-show="activeTab === 'ev'" class="bg-sf-surface rounded-sf shadow-sf overflow-hidden">
      <DataTable
        :value="store.evSessions"
        :loading="store.loadingEV"
        :rows="100"
        responsiveLayout="scroll"
        class="text-sm"
        :rowHover="true"
      >
        <Column field="started_at" header="Started" style="min-width: 160px">
          <template #body="{ data }">{{ fmtTs(data.started_at) }}</template>
        </Column>
        <Column field="ended_at" header="Ended" style="min-width: 160px" class="hidden md:table-cell">
          <template #body="{ data }">{{ data.ended_at ? fmtTs(data.ended_at) : '—' }}</template>
        </Column>
        <Column field="kwh_total" header="Total (kWh)" style="width: 110px">
          <template #body="{ data }">{{ fmtNum(data.kwh_total) }}</template>
        </Column>
        <Column field="kwh_solar" header="Solar (kWh)" style="width: 110px" class="hidden md:table-cell">
          <template #body="{ data }">{{ fmtNum(data.kwh_solar) }}</template>
        </Column>
        <Column field="kwh_grid" header="Grid (kWh)" style="width: 110px" class="hidden md:table-cell">
          <template #body="{ data }">{{ fmtNum(data.kwh_grid) }}</template>
        </Column>
        <Column field="cost_eur" header="Cost (€)" style="width: 90px">
          <template #body="{ data }">{{ fmtNum(data.cost_eur) }}</template>
        </Column>
        <Column field="savings_vs_gas_eur" header="Savings (€)" style="width: 100px" class="hidden md:table-cell">
          <template #body="{ data }">{{ fmtNum(data.savings_vs_gas_eur) }}</template>
        </Column>
        <Column header="" style="width: 80px" frozen alignFrozen="right">
          <template #body="{ data }">
            <div class="flex gap-1">
              <Button icon="pi pi-pencil" text rounded size="small" @click="openEditEV(data)" aria-label="Edit" />
              <Button icon="pi pi-trash" text rounded size="small" severity="danger" @click="confirmDeleteEV(data.id)" aria-label="Delete" />
            </div>
          </template>
        </Column>
      </DataTable>
    </div>

    <!-- Edit: Inverter Stat -->
    <Dialog
      v-model:visible="editInverterVisible"
      header="Edit Inverter Stat"
      modal
      :style="{ width: '90vw', maxWidth: '480px' }"
    >
      <div class="space-y-3 text-sm">
        <div class="text-sf-text-3 text-xs">
          <span class="font-medium">Inverter:</span> {{ editInverterDraft.inverter_id }}
          &nbsp;·&nbsp;
          <span class="font-medium">Time:</span> {{ fmtTs(editInverterDraft.timestamp) }}
        </div>
        <div class="space-y-2">
          <label class="block text-sf-text-2 font-medium">PV Yield (kWh)</label>
          <InputNumber v-model="editInverterDraft.pv_yield_today_kwh" :minFractionDigits="2" :maxFractionDigits="4" fluid />
        </div>
        <div class="space-y-2">
          <label class="block text-sf-text-2 font-medium">Feed-in (kWh)</label>
          <InputNumber v-model="editInverterDraft.feed_in_today_kwh" :minFractionDigits="2" :maxFractionDigits="4" fluid />
        </div>
        <div class="space-y-2">
          <label class="block text-sf-text-2 font-medium">Grid Buy (kWh)</label>
          <InputNumber v-model="editInverterDraft.grid_buy_today_kwh" :minFractionDigits="2" :maxFractionDigits="4" fluid />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="editInverterVisible = false" />
        <Button label="Save" @click="saveInverter" />
      </template>
    </Dialog>

    <!-- Edit: Meter Reading -->
    <Dialog
      v-model:visible="editMeterVisible"
      header="Edit Meter Reading"
      modal
      :style="{ width: '90vw', maxWidth: '480px' }"
    >
      <div class="space-y-3 text-sm">
        <div class="text-sf-text-3 text-xs">
          <span class="font-medium">Time:</span> {{ fmtTs(editMeterDraft.timestamp) }}
        </div>
        <Message severity="warn" :closable="false" class="text-xs">
          These are cumulative kWh counter values, not per-interval deltas. Editing affects all derived calculations.
        </Message>
        <div class="space-y-2">
          <label class="block text-sf-text-2 font-medium">Consumption (kWh)</label>
          <InputNumber v-model="editMeterDraft.consumption_kwh" :minFractionDigits="2" :maxFractionDigits="4" fluid />
        </div>
        <div class="space-y-2">
          <label class="block text-sf-text-2 font-medium">Feed-in (kWh)</label>
          <InputNumber v-model="editMeterDraft.feed_in_kwh" :minFractionDigits="2" :maxFractionDigits="4" fluid />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="editMeterVisible = false" />
        <Button label="Save" @click="saveMeter" />
      </template>
    </Dialog>

    <!-- Edit: EV Session -->
    <Dialog
      v-model:visible="editEVVisible"
      header="Edit EV Session"
      modal
      :style="{ width: '90vw', maxWidth: '480px' }"
    >
      <div class="space-y-3 text-sm">
        <div class="grid grid-cols-2 gap-3">
          <div class="space-y-1">
            <label class="block text-sf-text-2 font-medium">Started</label>
            <DatePicker v-model="editEVDraft.startedAt" showTime hourFormat="24" dateFormat="dd.mm.yy" fluid />
          </div>
          <div class="space-y-1">
            <label class="block text-sf-text-2 font-medium">Ended</label>
            <DatePicker v-model="editEVDraft.endedAt" showTime hourFormat="24" dateFormat="dd.mm.yy" fluid />
          </div>
        </div>
        <div class="space-y-2">
          <label class="block text-sf-text-2 font-medium">Total (kWh)</label>
          <InputNumber v-model="editEVDraft.kwh_total" :minFractionDigits="2" :maxFractionDigits="3" :min="0" fluid />
        </div>
        <div class="space-y-2">
          <label class="block text-sf-text-2 font-medium">Solar (kWh)</label>
          <InputNumber v-model="editEVDraft.kwh_solar" :minFractionDigits="2" :maxFractionDigits="3" :min="0" fluid />
        </div>
        <div class="space-y-2">
          <label class="block text-sf-text-2 font-medium">Grid (kWh)</label>
          <InputNumber v-model="editEVDraft.kwh_grid" :minFractionDigits="2" :maxFractionDigits="3" :min="0" fluid />
        </div>
        <div class="space-y-2">
          <label class="block text-sf-text-2 font-medium">Charging Power (kW)</label>
          <InputNumber v-model="editEVDraft.charging_power_kw" :minFractionDigits="1" :maxFractionDigits="2" :min="0" fluid />
        </div>
        <div class="space-y-2">
          <label class="block text-sf-text-2 font-medium">Cost (€)</label>
          <InputNumber v-model="editEVDraft.cost_eur" :minFractionDigits="2" :maxFractionDigits="2" :min="0" fluid />
        </div>
        <div class="space-y-2">
          <label class="block text-sf-text-2 font-medium">Savings vs Gas (€)</label>
          <InputNumber v-model="editEVDraft.savings_vs_gas_eur" :minFractionDigits="2" :maxFractionDigits="2" fluid />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" @click="editEVVisible = false" />
        <Button label="Save" @click="saveEV" />
      </template>
    </Dialog>

    <ConfirmDialog />
  </AppShell>
</template>
