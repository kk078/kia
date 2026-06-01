<template>
  <div class="mx-auto" style="max-width:820px">
    <!-- Header -->
    <div class="flex items-center justify-between mb-5">
      <div>
        <h1 style="font-size:1.9rem;font-weight:700">Chat</h1>
        <p style="color:var(--text-2);font-size:.9rem;margin-top:2px">Talk to KIA · runs locally</p>
      </div>
      <button @click="newChat" class="kia-btn-soft">
        <i class="fas fa-plus"></i> New chat
      </button>
    </div>

    <!-- Conversation -->
    <div class="kia-card kia-card-lg" style="display:flex;flex-direction:column;height:62vh;min-height:440px;overflow:hidden">
      <div ref="messagesContainer" class="flex-1 overflow-y-auto" style="padding:1.5rem">
        <!-- Empty state -->
        <div v-if="messages.length === 0" class="flex flex-col items-center justify-center text-center" style="height:100%;color:var(--text-2)">
          <KiaLogo :size="56" :wordmark="false" />
          <p style="font-size:1.15rem;font-weight:600;color:var(--text);margin-top:1rem">How can I help, Kiran?</p>
          <div class="flex flex-wrap justify-center gap-2" style="margin-top:1rem;max-width:520px">
            <span class="kia-hint"><code>/learn</code> teach KIA</span>
            <span class="kia-hint"><code>/brain</code> ask its memory</span>
            <span class="kia-hint"><code>/use</code> call connectors</span>
          </div>
        </div>

        <!-- Messages -->
        <div v-for="(msg, idx) in messages" :key="idx"
             class="kia-rise"
             :style="{ display:'flex', justifyContent: msg.role==='user' ? 'flex-end':'flex-start', marginBottom:'1rem' }">
          <div v-if="msg.role !== 'user'" class="shrink-0" style="margin-right:.6rem;margin-top:2px">
            <KiaLogo :size="26" :wordmark="false" />
          </div>
          <div :class="msg.role === 'user' ? 'kia-bubble-user' : 'kia-bubble-ai'">
            <div class="kia-bubble-text" v-html="render(msg.content)"></div>
          </div>
        </div>

        <!-- Typing -->
        <div v-if="loading" style="display:flex;align-items:center;margin-bottom:1rem">
          <div class="shrink-0" style="margin-right:.6rem"><KiaLogo :size="26" :wordmark="false" /></div>
          <div class="kia-bubble-ai" style="padding:.85rem 1rem">
            <span class="kia-dot"></span><span class="kia-dot"></span><span class="kia-dot"></span>
          </div>
        </div>
      </div>

      <!-- Composer -->
      <div style="border-top:1px solid var(--hairline);padding:.9rem 1rem;background:var(--surface-2)">
        <div class="flex items-end" style="gap:.6rem">
          <textarea
            v-model="input"
            @keydown.enter.exact.prevent="sendMessage"
            :disabled="loading"
            rows="1"
            ref="ta"
            @input="autoGrow"
            placeholder="Message KIA…"
            class="kia-textarea"
            style="max-height:140px;background:var(--surface)"
          ></textarea>
          <button @click="sendMessage" :disabled="loading || !input.trim()" class="kia-btn" style="padding:.7rem .9rem;border-radius:50%;width:44px;height:44px;flex-shrink:0">
            <i class="fas fa-arrow-up"></i>
          </button>
        </div>
        <!-- Task type segmented control -->
        <div class="flex items-center justify-between" style="margin-top:.7rem">
          <div class="kia-segment">
            <button v-for="type in taskTypes" :key="type"
                    @click="taskType = type"
                    :class="{ active: taskType === type }">{{ type }}</button>
          </div>
          <span style="color:var(--text-3);font-size:.78rem">↵ send · ⇧↵ newline</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import api from '../api'
import KiaLogo from '../components/KiaLogo.vue'

const messages = ref([])
const input = ref('')
const loading = ref(false)
const taskType = ref('simple')
const messagesContainer = ref(null)
const ta = ref(null)

const taskTypes = ['simple', 'fast', 'planning', 'research', 'synthesis', 'code']

// minimal, safe markdown-ish rendering (escape then apply a few patterns)
const render = (text) => {
  const esc = String(text)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return esc
    .replace(/```([\s\S]*?)```/g, '<pre class="kia-pre">$1</pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/_([^_]+)_/g, '<em>$1</em>')
    .replace(/\n/g, '<br>')
}

const autoGrow = () => {
  const el = ta.value
  if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 140) + 'px' }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  })
}

const pushUser = (c) => messages.value.push({ role: 'user', content: c })
const pushAI = (c) => messages.value.push({ role: 'assistant', content: c })
const errText = (e) => `Error: ${e.response?.data?.detail || e.message}`

const sendMessage = async () => {
  if (!input.value.trim() || loading.value) return
  const text = input.value.trim()
  input.value = ''
  nextTick(autoGrow)

  // /learn <text>
  if (text.toLowerCase().startsWith('/learn ')) {
    const body = text.slice(7).trim()
    pushUser('📚 Teaching KIA…'); loading.value = true; scrollToBottom()
    try {
      const r = await api.learn(body)
      pushAI(`Learned ✓ — indexed ${r.data.chunks_indexed} chunk(s). Ask about it with **/brain**; it's queued for my next training.`)
    } catch (e) { pushAI(errText(e)) } finally { loading.value = false; scrollToBottom() }
    return
  }
  // /use <task>
  if (text.toLowerCase().startsWith('/use ')) {
    const task = text.slice(5).trim()
    pushUser(task); loading.value = true; scrollToBottom()
    try {
      const r = await api.useConnectors(task)
      pushAI(r.data.answer + `\n\n_(via ${r.data.tools_available} connector tool(s))_`)
    } catch (e) { pushAI(errText(e)) } finally { loading.value = false; scrollToBottom() }
    return
  }
  // /brain <question>
  if (text.toLowerCase().startsWith('/brain ')) {
    const q = text.slice(7).trim()
    pushUser(q); loading.value = true; scrollToBottom()
    try {
      const r = await api.ragQuery(q)
      pushAI(r.data.answer)
    } catch (e) { pushAI(errText(e)) } finally { loading.value = false; scrollToBottom() }
    return
  }
  // normal chat
  pushUser(text); loading.value = true; scrollToBottom()
  try {
    const r = await api.generate(text, taskType.value)
    pushAI(r.data.response)
  } catch (e) { pushAI(errText(e)) } finally { loading.value = false; scrollToBottom() }
}

const newChat = () => { messages.value = []; input.value = ''; api.newSession() }
</script>

<style scoped>
.kia-hint { font-size:.82rem; color:var(--text-2); background:var(--fill); padding:.35rem .7rem; border-radius:980px; }
.kia-bubble-user {
  background: var(--kia-blue); color:#fff;
  padding:.7rem 1rem; border-radius:20px 20px 6px 20px; max-width:78%;
  box-shadow: var(--shadow-sm); font-size:.95rem; line-height:1.5;
}
.kia-bubble-ai {
  background: var(--surface); color:var(--text); border:1px solid var(--hairline);
  padding:.7rem 1rem; border-radius:20px 20px 20px 6px; max-width:82%;
  box-shadow: var(--shadow-sm); font-size:.95rem; line-height:1.55;
}
.kia-bubble-text :deep(pre.kia-pre) {
  background: var(--bg); border:1px solid var(--hairline); border-radius:10px;
  padding:.7rem .85rem; overflow-x:auto; font-family:"SF Mono",ui-monospace,Menlo,monospace;
  font-size:.82rem; margin:.5rem 0; white-space:pre-wrap;
}
.kia-bubble-user .kia-bubble-text :deep(code) { background: rgba(255,255,255,0.2); color:#fff; }
.kia-dot {
  display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--text-3);
  margin:0 2px; animation: kia-blink 1.2s infinite both;
}
.kia-dot:nth-child(2){ animation-delay:.2s } .kia-dot:nth-child(3){ animation-delay:.4s }
@keyframes kia-blink { 0%,80%,100%{ opacity:.25; transform:translateY(0) } 40%{ opacity:1; transform:translateY(-3px) } }
</style>
