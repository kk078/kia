<template>
  <div class="mx-auto" style="max-width:820px">
    <h1 style="font-size:1.9rem;font-weight:700;margin-bottom:.25rem">Orchestrator</h1>
    <p style="color:var(--text-2);font-size:.9rem;margin-bottom:1.5rem">Give KIA a complex goal — it plans, executes, and synthesizes</p>

    <div class="kia-card" style="padding:1.5rem;margin-bottom:1.25rem">
      <label class="kia-label">Goal</label>
      <textarea v-model="goal" rows="4" placeholder="Describe a complex goal. KIA breaks it into subtasks and executes them…" class="kia-textarea mb-3"></textarea>
      <label class="kia-label">Session ID</label>
      <input v-model="sessionId" placeholder="default" class="kia-input mb-4" />
      <button @click="runOrchestrator" :disabled="running" class="kia-btn" style="width:100%">
        <i :class="running ? 'fas fa-spinner fa-spin' : 'fas fa-play'"></i>
        {{ running ? 'Executing…' : 'Run orchestrator' }}
      </button>
    </div>

    <div v-if="result" class="kia-card kia-rise" style="padding:1.5rem">
      <h2 style="font-size:1.15rem;font-weight:600;margin-bottom:1rem"><i class="fas fa-circle-check" style="color:var(--green);margin-right:.5rem"></i>Result</h2>
      <p class="kia-label">Response</p>
      <div style="background:var(--surface-2);border:1px solid var(--hairline);border-radius:12px;padding:1rem;white-space:pre-wrap;font-size:.92rem;line-height:1.55;margin-bottom:1rem">{{ result.content }}</div>

      <div class="grid" style="grid-template-columns:1fr 1fr;gap:1rem">
        <div>
          <p class="kia-label">Confidence</p>
          <div style="background:var(--surface-2);border:1px solid var(--hairline);border-radius:12px;padding:1rem">
            <div class="flex justify-between mb-2" style="font-size:.9rem;font-weight:600">{{ (result.confidence*100).toFixed(0) }}%</div>
            <div style="background:var(--fill);border-radius:980px;height:8px;overflow:hidden">
              <div :style="{ width:`${result.confidence*100}%`, background:'var(--kia-blue)', height:'100%', borderRadius:'980px', transition:'width .4s ease' }"></div>
            </div>
          </div>
        </div>
        <div>
          <p class="kia-label">Sources</p>
          <div style="background:var(--surface-2);border:1px solid var(--hairline);border-radius:12px;padding:1rem">
            <ul style="list-style:disc;margin-left:1.1rem;font-size:.85rem">
              <li v-for="(src,i) in result.sources" :key="i">{{ src }}</li>
              <li v-if="!result.sources || result.sources.length===0" style="list-style:none;margin-left:-1.1rem;color:var(--text-3)">—</li>
            </ul>
          </div>
        </div>
      </div>

      <div v-if="result.metadata && Object.keys(result.metadata).length" style="margin-top:1rem">
        <p class="kia-label">Metadata</p>
        <pre style="background:var(--surface-2);border:1px solid var(--hairline);border-radius:12px;padding:1rem;font-size:.8rem;overflow-x:auto;font-family:'SF Mono',ui-monospace,Menlo,monospace">{{ JSON.stringify(result.metadata, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api'

const goal = ref(''); const sessionId = ref('default'); const running = ref(false); const result = ref(null)
const runOrchestrator = async () => {
  if (!goal.value.trim()) return
  running.value = true; result.value = null
  try { result.value = (await api.runOrchestrator(goal.value, sessionId.value || 'default')).data }
  catch (e) { result.value = { content: `Error: ${e.response?.data?.detail || e.message}`, confidence: 0, sources: [], metadata: {} } }
  finally { running.value = false }
}
</script>

<style scoped>
.kia-label { display:block; font-size:.8rem; font-weight:600; color:var(--text-2); margin-bottom:.35rem; }
</style>
