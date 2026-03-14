import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
    },
    {
      path: '/devices',
      name: 'devices',
      component: () => import('@/views/DevicesView.vue'),
    },
    {
      path: '/rules',
      name: 'rules',
      component: () => import('@/views/RulesView.vue'),
    },
    {
      path: '/rules/new',
      name: 'rule-create',
      component: () => import('@/views/RuleEditView.vue'),
    },
    {
      path: '/rules/:id/edit',
      name: 'rule-edit',
      component: () => import('@/views/RuleEditView.vue'),
    },
    {
      path: '/meter',
      name: 'meter',
      component: () => import('@/views/MeterView.vue'),
    },
  ],
})

export default router
