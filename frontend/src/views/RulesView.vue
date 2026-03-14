<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useRulesStore } from '@/stores/rules'
import AppShell from '@/components/layout/AppShell.vue'
import SectionHeader from '@/components/shared/SectionHeader.vue'
import EmptyState from '@/components/shared/EmptyState.vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import InputSwitch from 'primevue/inputswitch'
import Button from 'primevue/button'
import ConfirmDialog from 'primevue/confirmdialog'
import { useConfirm } from 'primevue/useconfirm'

const router = useRouter()
const store = useRulesStore()
const confirm = useConfirm()

onMounted(() => {
  store.fetchAll()
})

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never'
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'Yesterday'
  return `${days}d ago`
}

async function handleToggle(id: number) {
  await store.toggle(id)
}

function handleEdit(id: number) {
  router.push(`/rules/${id}/edit`)
}

function handleCreate() {
  router.push('/rules/new')
}

function handleDelete(id: number, name: string) {
  confirm.require({
    message: `Delete rule "${name}"? This cannot be undone.`,
    header: 'Delete Rule',
    icon: 'pi pi-trash',
    rejectLabel: 'Cancel',
    acceptLabel: 'Delete',
    acceptClass: 'p-button-danger',
    accept: () => store.remove(id),
  })
}
</script>

<template>
  <AppShell>
    <SectionHeader title="Rules">
      <template #actions>
        <Button label="Create" icon="pi pi-plus" size="small" @click="handleCreate" />
      </template>
    </SectionHeader>

    <div class="bg-sf-surface rounded-sf shadow-sf overflow-hidden">
      <template v-if="store.loading">
        <div class="p-6 space-y-3">
          <div v-for="i in 3" :key="i" class="h-12 bg-slate-50 rounded animate-pulse" />
        </div>
      </template>
      <template v-else-if="store.rules.length === 0">
        <EmptyState
          icon="pi pi-bolt"
          title="No rules yet"
          message="Create automation rules to control your devices based on solar production, battery level, and more."
          actionLabel="Create Rule"
          @action="handleCreate"
        />
      </template>
      <template v-else>
        <DataTable
          :value="store.rules"
          :rows="20"
          responsiveLayout="scroll"
          class="text-sm"
          :rowHover="true"
        >
          <Column field="name" header="Name" :sortable="true">
            <template #body="{ data }">
              <button
                @click="handleEdit(data.id)"
                class="font-medium text-sf-text-1 hover:text-sf-green-600 transition-colors bg-transparent border-0 cursor-pointer p-0 text-sm text-left"
              >
                {{ data.name }}
              </button>
            </template>
          </Column>
          <Column field="state" header="State" :sortable="true" style="width: 100px">
            <template #body="{ data }">
              <Tag
                :value="data.state === 'active' ? 'Active' : 'Idle'"
                :severity="data.state === 'active' ? 'success' : 'secondary'"
              />
            </template>
          </Column>
          <Column header="Last Fired" :sortable="true" class="hidden md:table-cell" style="width: 120px">
            <template #body="{ data }">
              <span class="text-sf-text-3 text-xs">{{ timeAgo(data.last_fired_at) }}</span>
            </template>
          </Column>
          <Column header="Enabled" style="width: 80px">
            <template #body="{ data }">
              <InputSwitch :modelValue="data.enabled" @update:modelValue="handleToggle(data.id)" />
            </template>
          </Column>
          <Column header="" style="width: 80px" class="hidden md:table-cell">
            <template #body="{ data }">
              <div class="flex gap-1">
                <Button icon="pi pi-pencil" text rounded size="small" @click="handleEdit(data.id)" aria-label="Edit" />
                <Button icon="pi pi-trash" text rounded size="small" severity="danger" @click="handleDelete(data.id, data.name)" aria-label="Delete" />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </div>

    <ConfirmDialog />
  </AppShell>
</template>
