<template>
  <div class="kia-chat-layout">
    <!-- History sidebar -->
    <aside class="kia-card kia-history">
      <div class="kia-history-head">
        <span style="font-weight:700">Chats</span>
        <button @click="newChat" class="kia-btn-soft" style="padding:.35rem .6rem;font-size:.82rem">
          <i class="fas fa-plus"></i> New
        </button>
      </div>
      <div class="kia-history-list">
        <div v-if="conversations.length === 0" style="color:var(--text-3);font-size:.85rem;padding:.6rem .4rem">
          No saved chats yet.
        </div>
        <button
          v-for="c in conversations" :key="c.id"
          @click="openConversation(c.id)"
          class="kia-history-item"
          :class="{ active: c.id === activeId }">
          <span class="kia-history-title">{{ c.title }}</span>
          <i class="fas fa-trash kia-history-del" @click.stop="deleteConv(c.id)" title="Delete"></i>
        </button>
      </div>
    </aside>

    <!-- Main chat -->
    <div class="kia-chat-main">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h1 style="font-size:1.9rem;font-weight:700">Chat</h1>
          <p style="color:var(--text-2);font-size:.9rem;margin-top:2px">Talk to KIA · runs locally · history saved</p>
        </div>
      </div>

      <!-- Degradation banner -->
      <div v-if="health && health.status !== 'healthy'" class="kia-banner" :class="health.status">
        <i class="fas" :class="health.status === 'critical' ? 'fa-triangle-exclamation' : 'fa-circle-info'"></i>
        <span>{{ (health.reasons && health.reasons[0]) || 'Some services are degraded.' }}</span>
      </div>

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
            <!-- Command plan / approval card -->
            <div v-if="msg.plan" class="kia-plan">
              <div class="kia-plan-head">
                <i class="fas fa-terminal"></i>
                <span>Proposed {{ msg.plan.commands.length }} command(s) for: <strong>{{ msg.plan.task }}</strong></span>
              </div>
              <div v-if="msg.plan.commands.length === 0" class="kia-plan-empty">
                KIA couldn't form a safe command plan for that. Try rephrasing, or it may be out of scope.
              </div>
              <div v-for="(c, ci) in msg.plan.commands" :key="ci" class="kia-cmd-row">
                <div class="kia-cmd-top">
                  <span class="kia-danger" :class="c.danger">{{ c.danger }}</span>
                  <code class="kia-cmd-code">{{ c.command }}</code>
                </div>
                <div v-if="c.explanation" class="kia-cmd-why">{{ c.explanation }}</div>
                <div v-if="c.status === 'running'" class="kia-cmd-out">running…</div>
                <pre v-else-if="c.output" class="kia-cmd-out" :class="{ bad: c.status === 'error' }">{{ c.output }}</pre>
              </div>
              <div v-if="msg.plan.state === 'review' && msg.plan.commands.length" class="kia-plan-actions">
                <button class="kia-btn" style="padding:.45rem .9rem;border-radius:10px" @click="runPlan(msg)">
                  <i class="fas fa-play"></i> Run {{ msg.plan.commands.length }} command(s)
                </button>
                <button class="kia-btn-soft" style="padding:.45rem .9rem" @click="msg.plan.state = 'cancelled'">Cancel</button>
              </div>
              <div v-else-if="msg.plan.state === 'running'" class="kia-plan-status">Running on host…</div>
              <div v-else-if="msg.plan.state === 'done'" class="kia-plan-status ok">Finished — review the output above.</div>
              <div v-else-if="msg.plan.state === 'cancelled'" class="kia-plan-status">Cancelled — nothing was run.</div>
            </div>
            <!-- Autonomous build panel -->
            <div v-else-if="msg.build" class="kia-build">
              <div class="kia-build-head">
                <i class="fas fa-robot"></i>
                <span>Building: <strong>{{ msg.build.goal }}</strong></span>
                <button v-if="msg.build.state === 'running' || msg.build.state === 'awaiting'"
                        class="kia-build-stop" @click="stopBuild(msg.build)">Stop</button>
              </div>
              <div v-if="msg.build.root" class="kia-build-root">in {{ msg.build.root }}</div>
              <div v-for="(e, ei) in msg.build.events" :key="ei" class="kia-evt">
                <div v-if="e.type === 'thought'" class="kia-evt-thought"><i class="fas fa-comment-dots"></i> {{ e.content }}</div>
                <div v-else-if="e.type === 'action'" class="kia-evt-action">
                  <span class="kia-evt-tool">{{ e.tool }}</span>
                  <span class="kia-danger" :class="e.danger">{{ e.danger }}</span>
                  <code>{{ e.preview }}</code>
                </div>
                <pre v-else-if="e.type === 'observation'" class="kia-evt-obs" :class="{ bad: !e.ok }">{{ e.content }}</pre>
                <div v-else-if="e.type === 'approval'" class="kia-evt-approval">
                  <div class="kia-evt-approval-head"><i class="fas fa-triangle-exclamation"></i> Approve this high-risk command?</div>
                  <code class="kia-cmd-code">{{ e.command }}</code>
                  <div v-if="msg.build.pending && msg.build.state === 'awaiting'" class="kia-plan-actions">
                    <button class="kia-btn" style="padding:.4rem .8rem;border-radius:10px" @click="decideBuild(msg.build, true)">Approve &amp; run</button>
                    <button class="kia-btn-soft" style="padding:.4rem .8rem" @click="decideBuild(msg.build, false)">Reject</button>
                  </div>
                </div>
                <div v-else-if="e.type === 'finish'" class="kia-evt-finish"><i class="fas fa-circle-check"></i> {{ e.summary }}</div>
                <div v-else-if="e.type === 'limit'" class="kia-evt-warn">{{ e.content }}</div>
                <div v-else-if="e.type === 'error'" class="kia-evt-err">{{ e.content }}</div>
              </div>
              <div v-if="msg.build.state === 'running'" class="kia-build-status">
                <span class="kia-dot"></span><span class="kia-dot"></span><span class="kia-dot"></span> working…
              </div>
            </div>
            <!-- Normal bubble -->
            <div v-else :class="msg.role === 'user' ? 'kia-bubble-user' : 'kia-bubble-ai'">
              <div class="kia-bubble-text" v-html="render(msg.content)"></div>
              <span v-if="msg.streaming && !msg.content" class="kia-dot"></span>
              <span v-if="msg.streaming && !msg.content" class="kia-dot"></span>
              <span v-if="msg.streaming && !msg.content" class="kia-dot"></span>
              <span v-if="msg.streaming && msg.content" class="kia-caret">▍</span>
            </div>
          </div>

          <!-- Non-stream loading (slash commands) -->
          <div v-if="loading" style="display:flex;align-items:center;margin-bottom:1rem">
            <div class="shrink-0" style="margin-right:.6rem"><KiaLogo :size="26" :wordmark="false" /></div>
            <div class="kia-bubble-ai" style="padding:.85rem 1rem">
              <span class="kia-dot"></span><span class="kia-dot"></span><span class="kia-dot"></span>
            </div>
          </div>
        </div>

        <!-- Composer -->
        <div style="border-top:1px solid var(--hairline);padding:.9rem 1rem;background:var(--surface-2);position:relative">
          <!-- Slash-command menu -->
          <div v-if="showMenu" class="kia-cmd-menu">
            <button
              v-for="(c, i) in filteredCommands" :key="c.cmd"
              class="kia-cmd-item" :class="{ active: i === menuIndex }"
              @mousedown.prevent="selectAt(i)"
              @mouseenter="menuIndex = i">
              <code class="kia-cmd-name">{{ c.cmd }}</code>
              <span class="kia-cmd-desc">{{ c.desc }}</span>
            </button>
          </div>
          <div class="flex items-end" style="gap:.6rem">
            <textarea
              v-model="input"
              @keydown.enter.exact.prevent="onEnter"
              @keydown.down="onArrow($event, 1)"
              @keydown.up="onArrow($event, -1)"
              @keydown.tab="onTab($event)"
              @keydown.esc="menuOpen = false"
              :disabled="loading || streaming"
              rows="1"
              ref="ta"
              @input="onInput"
              placeholder="Message KIA…  (type / for commands)"
              class="kia-textarea"
              style="max-height:140px;background:var(--surface)"
            ></textarea>
            <button @click="sendMessage" :disabled="loading || streaming || !input.trim()" class="kia-btn" style="padding:.7rem .9rem;border-radius:50%;width:44px;height:44px;flex-shrink:0">
              <i class="fas fa-arrow-up"></i>
            </button>
          </div>
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
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import api from '../api'
import KiaLogo from '../components/KiaLogo.vue'

const messages = ref([])
const conversations = ref([])
const activeId = ref(null)
const input = ref('')
const loading = ref(false)
const streaming = ref(false)
const taskType = ref('simple')
const health = ref(null)
const messagesContainer = ref(null)
const ta = ref(null)

const taskTypes = ['simple', 'fast', 'planning', 'research', 'code']

// Slash-command autocomplete
const commands = [
  { cmd: '/learn', desc: 'Teach KIA — add text to its knowledge base' },
  { cmd: '/brain', desc: 'Ask KIA from its knowledge base (retrieval)' },
  { cmd: '/use', desc: 'Call connector tools (GitHub, web, Slack…)' },
  { cmd: '/build', desc: 'Plan & run commands on this computer (you approve each)' },
  { cmd: '/agent', desc: 'Autonomous build — KIA writes files & runs commands to do it' }
]
const menuOpen = ref(false)
const menuIndex = ref(0)

const filteredCommands = computed(() => {
  const v = input.value
  if (!v.startsWith('/') || v.includes(' ')) return []
  const q = v.slice(1).toLowerCase()
  return commands.filter(c => c.cmd.slice(1).toLowerCase().startsWith(q))
})
const showMenu = computed(() => menuOpen.value && filteredCommands.value.length > 0)

const onInput = () => {
  autoGrow()
  const v = input.value
  menuOpen.value = v.startsWith('/') && !v.includes(' ')
  menuIndex.value = 0
}
const menuMove = (d) => {
  const n = filteredCommands.value.length
  if (n) menuIndex.value = (menuIndex.value + d + n) % n
}
const onArrow = (e, d) => { if (!showMenu.value) return; e.preventDefault(); menuMove(d) }
const acceptCommand = () => {
  const c = filteredCommands.value[menuIndex.value]
  if (!c) return
  input.value = c.cmd + ' '
  menuOpen.value = false
  nextTick(() => { if (ta.value) ta.value.focus(); autoGrow() })
}
const selectAt = (i) => { menuIndex.value = i; acceptCommand() }
const onEnter = () => { if (showMenu.value) acceptCommand(); else sendMessage() }
const onTab = (e) => { if (showMenu.value) { e.preventDefault(); acceptCommand() } }

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

const loadConversations = async () => {
  try { conversations.value = (await api.listConversations()).data || [] } catch { /* offline ok */ }
}

const openConversation = async (id) => {
  if (streaming.value || loading.value) return
  try {
    const r = await api.getConversation(id)
    activeId.value = id
    messages.value = (r.data.messages || []).map(m => ({ role: m.role, content: m.content }))
    scrollToBottom()
  } catch (e) { pushAI(errText(e)) }
}

const deleteConv = async (id) => {
  try {
    await api.deleteConversation(id)
    if (id === activeId.value) newChat()
    await loadConversations()
  } catch { /* ignore */ }
}

// Ensure a conversation exists (slash commands don't go through the stream endpoint,
// which is what normally creates one).
const ensureConversation = async () => {
  if (!activeId.value) {
    const r = await api.createConversation()
    activeId.value = r.data.id
  }
  return activeId.value
}

// Persist a non-streamed turn (slash commands) to durable history. Best-effort.
const persistTurn = async (userText, assistantText) => {
  try {
    const id = await ensureConversation()
    await api.appendMessages(id, [
      { role: 'user', content: userText },
      { role: 'assistant', content: assistantText }
    ])
    await loadConversations()
  } catch { /* history is best-effort */ }
}

const sendMessage = async () => {
  if (!input.value.trim() || loading.value || streaming.value) return
  const text = input.value.trim()
  input.value = ''
  nextTick(autoGrow)

  // /learn <text>
  if (text.toLowerCase().startsWith('/learn ')) {
    const body = text.slice(7).trim()
    pushUser('📚 Teaching KIA…'); loading.value = true; scrollToBottom()
    try {
      const r = await api.learn(body)
      const ans = `Learned ✓ — indexed ${r.data.chunks_indexed} chunk(s). Ask about it with **/brain**; it's queued for my next training.`
      pushAI(ans)
      persistTurn(text, ans)
    } catch (e) { pushAI(errText(e)) } finally { loading.value = false; scrollToBottom() }
    return
  }
  // /use <task>
  if (text.toLowerCase().startsWith('/use ')) {
    const task = text.slice(5).trim()
    pushUser(task); loading.value = true; scrollToBottom()
    try {
      const r = await api.useConnectors(task)
      const ans = r.data.answer + `\n\n_(via ${r.data.tools_available} connector tool(s))_`
      pushAI(ans)
      persistTurn(task, ans)
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
      persistTurn(q, r.data.answer)
    } catch (e) { pushAI(errText(e)) } finally { loading.value = false; scrollToBottom() }
    return
  }
  // /build <task>  — propose host commands you approve before they run
  if (text.toLowerCase().startsWith('/build ')) {
    const task = text.slice(7).trim()
    pushUser(task); loading.value = true; scrollToBottom()
    try {
      const r = await api.execPlan(task)
      messages.value.push({
        role: 'assistant',
        plan: {
          id: r.data.plan_id,
          task,
          os: r.data.os,
          commands: (r.data.commands || []).map(c => ({ ...c, status: 'pending', output: '' })),
          state: 'review'
        }
      })
    } catch (e) {
      const extra = e.response?.status === 503
        ? ' — set EXEC_ENABLED=true in .env and start host_runner/runner.py on this machine.'
        : ''
      pushAI(errText(e) + extra)
    } finally { loading.value = false; scrollToBottom() }
    return
  }

  // /agent <goal>  — autonomous build loop (think → act → observe), streamed live
  if (text.toLowerCase().startsWith('/agent ')) {
    const goal = text.slice(7).trim()
    // /agent continue — resume the most recent build that hit its step budget
    if (goal.toLowerCase() === 'continue') {
      const prev = [...messages.value].reverse().find(m => m.build && m.build.sessionId)
      if (!prev) { pushUser(text); pushAI('No previous build to continue.'); scrollToBottom(); return }
      pushUser('continue build')
      prev.build.state = 'running'
      streaming.value = true
      scrollToBottom()
      try {
        await api.continueBuild(prev.build.sessionId, (evt) => handleBuildEvent(prev.build, evt))
      } catch (e) {
        prev.build.events.push({ type: 'error', content: errText(e) })
      } finally {
        if (prev.build.state === 'running') prev.build.state = 'done'
        streaming.value = false
        scrollToBottom()
      }
      return
    }
    pushUser(goal)
    const msg = { role: 'assistant', build: { goal, root: null, sessionId: null, events: [], state: 'running' } }
    messages.value.push(msg)
    streaming.value = true
    scrollToBottom()
    try {
      await api.startBuild(goal, null, (evt) => handleBuildEvent(msg.build, evt))
    } catch (e) {
      msg.build.events.push({ type: 'error', content: errText(e) })
    } finally {
      if (msg.build.state === 'running') msg.build.state = 'done'
      streaming.value = false
      scrollToBottom()
    }
    return
  }

  // Normal chat — streamed + persisted to durable history.
  pushUser(text)
  const aiMsg = { role: 'assistant', content: '', streaming: true }
  messages.value.push(aiMsg)
  streaming.value = true
  scrollToBottom()
  try {
    const result = await api.streamChat(text, {
      conversationId: activeId.value,
      taskType: taskType.value,
      onToken: (t) => { aiMsg.content += t; scrollToBottom() }
    })
    aiMsg.streaming = false
    const wasNew = !activeId.value
    if (result.conversationId) activeId.value = result.conversationId
    if (wasNew) await loadConversations()
  } catch (e) {
    aiMsg.streaming = false
    if (!aiMsg.content) aiMsg.content = errText(e)
  } finally {
    streaming.value = false
    scrollToBottom()
  }
}

// Execute an approved command plan, command by command, on the host.
const runPlan = async (msg) => {
  const plan = msg.plan
  plan.state = 'running'
  const results = []
  for (let i = 0; i < plan.commands.length; i++) {
    const c = plan.commands[i]
    c.status = 'running'; scrollToBottom()
    try {
      const d = (await api.execRun(plan.id, i)).data
      c.status = d.ok ? 'done' : 'error'
      c.output = `exit ${d.exit_code}` + (d.stdout ? `\n${d.stdout}` : '') + (d.stderr ? `\n${d.stderr}` : '')
      results.push({ command: d.command, exit_code: d.exit_code, stdout: d.stdout, stderr: d.stderr })
    } catch (e) {
      c.status = 'error'; c.output = errText(e)
      results.push({ command: c.command, exit_code: -1, stdout: '', stderr: errText(e) })
    }
    scrollToBottom()
  }
  plan.state = 'done'; scrollToBottom()
  // Summarize what actually happened (installed / already present / failed) in plain language.
  let summary = `Ran ${plan.commands.length} command(s) for "${plan.task}".`
  try {
    summary = (await api.execSummary(plan.task, results)).data.summary || summary
  } catch { /* fall back to the generic line */ }
  pushAI(summary)
  persistTurn('/build ' + plan.task, summary)
}

// --- Autonomous build agent ---
const handleBuildEvent = (build, evt) => {
  if (evt.type === 'meta') {
    build.sessionId = evt.session_id; build.root = evt.root
  } else if (evt.type === 'approval') {
    build.pending = evt; build.state = 'awaiting'; build.events.push(evt)
  } else {
    build.events.push(evt)
    if (evt.type === 'finish' || evt.type === 'limit') build.state = 'done'
  }
  scrollToBottom()
}

const decideBuild = async (build, approve) => {
  build.pending = null; build.state = 'running'; scrollToBottom()
  try {
    await api.resumeBuild(build.sessionId, approve, (evt) => handleBuildEvent(build, evt))
  } catch (e) {
    build.events.push({ type: 'error', content: errText(e) })
  } finally {
    if (build.state === 'running') build.state = 'done'
    streaming.value = false
    scrollToBottom()
  }
}

const stopBuild = (build) => {
  if (build.sessionId) api.cancelBuild(build.sessionId).catch(() => {})
  build.state = 'stopped'; build.pending = null
  build.events.push({ type: 'error', content: 'Stopped by you.' })
  streaming.value = false
}

const newChat = () => {
  messages.value = []; input.value = ''; activeId.value = null; api.newSession()
}

onMounted(async () => {
  loadConversations()
  try { health.value = (await api.deepHealth()).data } catch { /* health is best-effort */ }
})
</script>

<style scoped>
.kia-chat-layout { display:flex; gap:1rem; align-items:flex-start; max-width:1100px; margin:0 auto; }
.kia-chat-main { flex:1; min-width:0; }
.kia-history { width:240px; flex-shrink:0; padding:.9rem; display:flex; flex-direction:column; max-height:74vh; }
.kia-history-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:.6rem; }
.kia-history-list { overflow-y:auto; display:flex; flex-direction:column; gap:2px; }
.kia-history-item {
  display:flex; align-items:center; justify-content:space-between; gap:.4rem;
  text-align:left; padding:.5rem .6rem; border-radius:10px; font-size:.86rem;
  color:var(--text); background:transparent; border:none; cursor:pointer; width:100%;
}
.kia-history-item:hover { background:var(--fill); }
.kia-history-item.active { background:var(--kia-blue); color:#fff; }
.kia-history-title { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1; }
.kia-history-del { opacity:0; font-size:.78rem; color:inherit; flex-shrink:0; }
.kia-history-item:hover .kia-history-del { opacity:.6; }
.kia-history-del:hover { opacity:1 !important; }
.kia-banner {
  display:flex; align-items:center; gap:.55rem; padding:.6rem .85rem; border-radius:12px;
  font-size:.85rem; margin-bottom:.8rem;
}
.kia-banner.degraded { background:#fff4e0; color:#8a5a00; border:1px solid #f3d28a; }
.kia-banner.critical { background:#fde8e8; color:#a01919; border:1px solid #f0b4b4; }
.kia-hint { font-size:.82rem; color:var(--text-2); background:var(--fill); padding:.35rem .7rem; border-radius:980px; }
.kia-cmd-menu {
  position:absolute; left:1rem; right:1rem; bottom:100%; margin-bottom:.5rem;
  background:var(--surface); border:1px solid var(--hairline); border-radius:14px;
  box-shadow:0 8px 30px rgba(0,0,0,.12); padding:.35rem; z-index:20;
}
.kia-cmd-item {
  display:flex; align-items:baseline; gap:.6rem; width:100%; text-align:left;
  padding:.5rem .7rem; border:none; background:transparent; border-radius:10px; cursor:pointer;
}
.kia-cmd-item.active { background:var(--fill); }
.kia-cmd-name { color:var(--kia-blue); font-weight:600; font-size:.9rem; font-family:"SF Mono",ui-monospace,Menlo,monospace; }
.kia-cmd-desc { color:var(--text-2); font-size:.82rem; }
.kia-plan {
  background:var(--surface); border:1px solid var(--hairline); border-radius:16px;
  padding:1rem; max-width:92%; box-shadow:var(--shadow-sm); font-size:.9rem;
}
.kia-plan-head { display:flex; align-items:center; gap:.5rem; color:var(--text); font-weight:600; margin-bottom:.7rem; }
.kia-plan-head i { color:var(--kia-blue); }
.kia-plan-empty { color:var(--text-2); font-size:.85rem; }
.kia-cmd-row { border-top:1px solid var(--hairline); padding:.6rem 0; }
.kia-cmd-row:first-of-type { border-top:none; padding-top:0; }
.kia-cmd-top { display:flex; align-items:flex-start; gap:.5rem; }
.kia-cmd-code {
  font-family:"SF Mono",ui-monospace,Menlo,monospace; font-size:.82rem; color:var(--text);
  background:var(--bg); border:1px solid var(--hairline); border-radius:8px; padding:.3rem .5rem;
  white-space:pre-wrap; word-break:break-all; flex:1;
}
.kia-cmd-why { color:var(--text-2); font-size:.8rem; margin:.35rem 0 0 .2rem; }
.kia-cmd-out {
  margin-top:.4rem; background:var(--bg); border:1px solid var(--hairline); border-radius:8px;
  padding:.5rem .6rem; font-family:"SF Mono",ui-monospace,Menlo,monospace; font-size:.78rem;
  white-space:pre-wrap; max-height:220px; overflow:auto; color:var(--text-2);
}
.kia-cmd-out.bad { border-color:#f0b4b4; background:#fff5f5; color:#a01919; }
.kia-danger { font-size:.68rem; font-weight:700; text-transform:uppercase; padding:.15rem .4rem; border-radius:6px; flex-shrink:0; margin-top:.2rem; }
.kia-danger.low { background:#e6f4ea; color:#1e7a34; }
.kia-danger.medium { background:#fff4e0; color:#8a5a00; }
.kia-danger.high { background:#fde8e8; color:#a01919; }
.kia-plan-actions { display:flex; gap:.5rem; margin-top:.8rem; }
.kia-plan-status { margin-top:.7rem; font-size:.83rem; color:var(--text-2); }
.kia-plan-status.ok { color:#1e7a34; }
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
.kia-caret { display:inline-block; margin-left:1px; animation: kia-caret 1s steps(1) infinite; color:var(--text-3); }
@keyframes kia-caret { 50% { opacity:0; } }
.kia-dot {
  display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--text-3);
  margin:0 2px; animation: kia-blink 1.2s infinite both;
}
.kia-dot:nth-child(2){ animation-delay:.2s } .kia-dot:nth-child(3){ animation-delay:.4s }
@keyframes kia-blink { 0%,80%,100%{ opacity:.25; transform:translateY(0) } 40%{ opacity:1; transform:translateY(-3px) } }
/* Autonomous build panel */
.kia-build {
  background:var(--surface); border:1px solid var(--hairline); border-radius:16px;
  padding:1rem; max-width:92%; box-shadow:var(--shadow-sm); font-size:.9rem;
}
.kia-build-head { display:flex; align-items:center; gap:.5rem; font-weight:600; }
.kia-build-head i { color:var(--kia-blue); }
.kia-build-stop {
  margin-left:auto; font-size:.78rem; padding:.25rem .6rem; border-radius:8px;
  border:1px solid #f0b4b4; background:#fff5f5; color:#a01919; cursor:pointer;
}
.kia-build-root { color:var(--text-3); font-size:.78rem; margin:.2rem 0 .6rem; font-family:"SF Mono",ui-monospace,Menlo,monospace; }
.kia-evt { margin:.35rem 0; }
.kia-evt-thought { color:var(--text-2); font-style:italic; }
.kia-evt-thought i { color:var(--text-3); margin-right:.3rem; }
.kia-evt-action { display:flex; align-items:center; gap:.45rem; flex-wrap:wrap; }
.kia-evt-tool {
  font-size:.72rem; font-weight:700; text-transform:uppercase; color:var(--kia-blue-deep);
  background:var(--fill); padding:.12rem .4rem; border-radius:6px;
}
.kia-evt-action code {
  font-family:"SF Mono",ui-monospace,Menlo,monospace; font-size:.8rem; color:var(--text);
  background:var(--bg); border:1px solid var(--hairline); border-radius:7px; padding:.2rem .45rem;
  white-space:pre-wrap; word-break:break-all; flex:1; min-width:0;
}
.kia-evt-obs {
  margin:.3rem 0 .5rem; background:var(--bg); border:1px solid var(--hairline); border-radius:8px;
  padding:.45rem .6rem; font-family:"SF Mono",ui-monospace,Menlo,monospace; font-size:.76rem;
  white-space:pre-wrap; max-height:240px; overflow:auto; color:var(--text-2);
}
.kia-evt-obs.bad { border-color:#f0b4b4; background:#fff5f5; color:#a01919; }
.kia-evt-approval {
  background:#fff4e0; border:1px solid #f3d28a; border-radius:10px; padding:.6rem .7rem; margin:.4rem 0;
}
.kia-evt-approval-head { color:#8a5a00; font-weight:600; margin-bottom:.4rem; }
.kia-evt-finish { color:#1e7a34; font-weight:600; margin-top:.4rem; }
.kia-evt-finish i { margin-right:.3rem; }
.kia-evt-warn { color:#8a5a00; }
.kia-evt-err { color:#a01919; }
.kia-build-status { color:var(--text-3); font-size:.82rem; margin-top:.4rem; }
@media (max-width: 760px) {
  .kia-chat-layout { flex-direction:column; }
  .kia-history { width:100%; max-height:30vh; }
}
</style>
