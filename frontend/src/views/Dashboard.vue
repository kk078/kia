<template>
  <div class="mx-auto" style="max-width:980px">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 style="font-size:1.9rem;font-weight:700;margin-bottom:.25rem">Dashboard</h1>
        <p style="color:var(--text-2);font-size:.9rem">System health · v{{ status.version }} · {{ status.environment }}</p>
      </div>
      <button @click="refreshStatus" class="kia-btn-soft"><i class="fas fa-rotate"></i> Refresh</button>
    </div>

    <!-- Service cards -->
    <div class="grid mb-6" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem">
      <div v-for="s in services" :key="s.name" class="kia-card" style="padding:1.25rem">
        <div class="flex items-center justify-between mb-1">
          <h3 style="font-size:1.05rem;font-weight:600">{{ s.name }}</h3>
          <span class="kia-status-dot" :style="{ background: s.healthy ? 'var(--green)' : 'var(--red)' }"></span>
        </div>
        <p style="font-size:.8rem;color:var(--text-3)">{{ s.url }}</p>
        <p :style="{ color: s.healthy ? '#1a7f37' : '#c4271f', fontSize:'.85rem', fontWeight:600, marginTop:'.5rem' }">
          {{ s.healthy ? 'Healthy' : 'Unreachable' }}
        </p>
      </div>
    </div>

    <!-- Quick actions -->
    <div class="kia-card" style="padding:1.5rem">
      <h2 style="font-size:1.15rem;font-weight:600;margin-bottom:1rem">Quick actions</h2>
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.75rem">
        <router-link to="/chat" class="kia-action"><i class="fas fa-comment" style="color:var(--kia-blue)"></i><span>Chat</span></router-link>
        <router-link to="/memory" class="kia-action"><i class="fas fa-layer-group" style="color:var(--purple)"></i><span>Memory</span></router-link>
        <router-link to="/knowledge" class="kia-action"><i class="fas fa-book" style="color:var(--green)"></i><span>Knowledge</span></router-link>
        <router-link to="/orchestrator" class="kia-action"><i class="fas fa-diagram-project" style="color:var(--orange)"></i><span>Orchestrator</span></router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const services = ref([
  { name: 'API', url: 'localhost:8000', healthy: false },
  { name: 'Redis', url: 'localhost:6379', healthy: false },
  { name: 'Weaviate', url: 'localhost:8081', healthy: false },
  { name: 'FalkorDB', url: 'localhost:6380', healthy: false }
])
const status = ref({ version: '0.1.0', environment: 'development' })

const refreshStatus = async () => {
  try {
    const h = await api.health()
    services.value[0].healthy = h.data.status === 'healthy'
    const s = await api.status()
    status.value = s.data
    services.value[1].healthy = true
    services.value[2].healthy = true
    services.value[3].healthy = true
  } catch (e) { console.error(e); services.value[0].healthy = false }
}
onMounted(refreshStatus)
</script>

<style scoped>
.kia-status-dot { width:11px; height:11px; border-radius:50%; box-shadow:0 0 0 4px rgba(0,0,0,0.04); }
.kia-action {
  display:flex; flex-direction:column; align-items:center; gap:.5rem;
  background:var(--surface-2); border:1px solid var(--hairline); border-radius:14px;
  padding:1.1rem; text-decoration:none; color:var(--text); font-size:.9rem; font-weight:500;
  transition: all .15s ease;
}
.kia-action i { font-size:1.5rem; }
.kia-action:hover { background:var(--fill); transform:translateY(-2px); box-shadow:var(--shadow-sm); }
</style>
