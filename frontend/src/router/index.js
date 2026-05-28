import { createRouter, createWebHistory } from 'vue-router'
import Chat from '../views/Chat.vue'
import Memory from '../views/Memory.vue'
import Knowledge from '../views/Knowledge.vue'
import Dashboard from '../views/Dashboard.vue'
import Orchestrator from '../views/Orchestrator.vue'

const routes = [
  { path: '/', redirect: '/chat' },
  { path: '/chat', name: 'Chat', component: Chat },
  { path: '/memory', name: 'Memory', component: Memory },
  { path: '/knowledge', name: 'Knowledge', component: Knowledge },
  { path: '/dashboard', name: 'Dashboard', component: Dashboard },
  { path: '/orchestrator', name: 'Orchestrator', component: Orchestrator }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
