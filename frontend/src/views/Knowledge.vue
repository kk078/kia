<template>
  <div class="mx-auto" style="max-width:980px">
    <h1 style="font-size:1.9rem;font-weight:700;margin-bottom:.25rem">Knowledge</h1>
    <p style="color:var(--text-2);font-size:.9rem;margin-bottom:1.5rem">Index documents and query KIA's knowledge base</p>

    <div class="grid" style="grid-template-columns:1fr 1fr;gap:1.25rem">
      <!-- Index -->
      <div class="kia-card" style="padding:1.5rem">
        <h2 style="font-size:1.15rem;font-weight:600;margin-bottom:1rem"><i class="fas fa-circle-plus" style="color:var(--green);margin-right:.5rem"></i>Index document</h2>
        <label class="kia-label">Source</label>
        <input v-model="docSource" placeholder="e.g. manual, notes.txt" class="kia-input mb-3" />
        <label class="kia-label">Content</label>
        <textarea v-model="docContent" rows="7" placeholder="Paste document content…" class="kia-textarea mb-3"></textarea>
        <button @click="indexDocument" :disabled="indexing" class="kia-btn" style="width:100%">
          <i :class="indexing ? 'fas fa-spinner fa-spin' : 'fas fa-arrow-up-from-bracket'"></i>
          {{ indexing ? 'Indexing…' : 'Index document' }}
        </button>
        <div v-if="indexResult" class="kia-rise" style="margin-top:.9rem;background:rgba(52,199,89,.1);border:1px solid rgba(52,199,89,.25);border-radius:12px;padding:.8rem;color:#1a7f37;font-size:.9rem">
          <i class="fas fa-circle-check" style="margin-right:.4rem"></i>Indexed {{ indexResult.chunk_ids?.length || 0 }} chunk(s)
        </div>
      </div>

      <!-- RAG -->
      <div class="kia-card" style="padding:1.5rem">
        <h2 style="font-size:1.15rem;font-weight:600;margin-bottom:1rem"><i class="fas fa-magnifying-glass" style="color:var(--kia-blue);margin-right:.5rem"></i>Ask the knowledge base</h2>
        <label class="kia-label">Question</label>
        <textarea v-model="ragQuestion" rows="4" placeholder="Ask about your indexed knowledge…" class="kia-textarea mb-3"></textarea>
        <button @click="queryRAG" :disabled="querying" class="kia-btn" style="width:100%">
          <i :class="querying ? 'fas fa-spinner fa-spin' : 'fas fa-wand-magic-sparkles'"></i>
          {{ querying ? 'Thinking…' : 'Ask' }}
        </button>
        <div v-if="ragAnswer" class="kia-rise" style="margin-top:.9rem;background:var(--surface-2);border:1px solid var(--hairline);border-radius:12px;padding:.9rem">
          <p style="font-size:.8rem;color:var(--text-3);margin-bottom:.4rem;font-weight:600">ANSWER</p>
          <p style="white-space:pre-wrap;font-size:.92rem;line-height:1.55">{{ ragAnswer }}</p>
        </div>
      </div>
    </div>

    <!-- Context retrieval -->
    <div class="kia-card" style="padding:1.5rem;margin-top:1.25rem">
      <h2 style="font-size:1.15rem;font-weight:600;margin-bottom:1rem"><i class="fas fa-layer-group" style="color:var(--purple);margin-right:.5rem"></i>Context retrieval</h2>
      <div class="flex gap-2 mb-4">
        <input v-model="contextQuery" @keyup.enter="retrieveContext" placeholder="Find relevant chunks…" class="kia-input" />
        <button @click="retrieveContext" class="kia-btn"><i class="fas fa-magnifying-glass"></i></button>
      </div>
      <div class="space-y-3">
        <div v-for="(chunk,idx) in contextChunks" :key="idx" class="kia-rise" style="background:var(--surface-2);border:1px solid var(--hairline);border-radius:12px;padding:.9rem">
          <div class="flex justify-between items-center mb-1.5">
            <span style="font-size:.8rem;color:var(--text-3)">{{ chunk.document_id }}</span>
            <span style="font-size:.72rem;background:rgba(94,92,230,.14);color:#4b49c4;padding:.15rem .5rem;border-radius:980px">Chunk {{ idx+1 }}</span>
          </div>
          <p style="font-size:.88rem;line-height:1.5">{{ chunk.content }}</p>
        </div>
        <p v-if="contextChunks.length===0 && contextQuery" style="text-align:center;color:var(--text-3);padding:2rem 0">No context found</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api'

const docSource = ref(''); const docContent = ref(''); const indexing = ref(false); const indexResult = ref(null)
const indexDocument = async () => {
  if (!docContent.value.trim()) return
  indexing.value = true
  try { indexResult.value = (await api.indexDocument(docContent.value, docSource.value||'manual')).data; docContent.value=''; docSource.value='' }
  catch(e){ console.error(e) } finally { indexing.value=false }
}
const ragQuestion = ref(''); const querying = ref(false); const ragAnswer = ref('')
const queryRAG = async () => {
  if (!ragQuestion.value.trim()) return
  querying.value=true; ragAnswer.value=''
  try { ragAnswer.value = (await api.ragQuery(ragQuestion.value)).data.answer }
  catch(e){ ragAnswer.value = `Error: ${e.response?.data?.detail || e.message}` } finally { querying.value=false }
}
const contextQuery = ref(''); const contextChunks = ref([])
const retrieveContext = async () => {
  if (!contextQuery.value.trim()) return
  try { contextChunks.value = (await api.retrieveContext(contextQuery.value)).data } catch(e){ console.error(e) }
}
</script>

<style scoped>
.kia-label { display:block; font-size:.8rem; font-weight:600; color:var(--text-2); margin-bottom:.35rem; }
</style>
