import axios from 'axios'
import { setDegraded } from './state'

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json'
  }
})

// Session id groups a conversation's traces in Langfuse Sessions.
// Call newSession() when starting a new chat so each conversation is its own session.
const genId = () =>
  (typeof crypto !== 'undefined' && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now())
let sessionId = genId()

export default {
  // Start a new conversation/session (new Langfuse session grouping)
  newSession() {
    sessionId = genId()
    return sessionId
  },
  currentSession() {
    return sessionId
  },

  // LLM
  async generate(prompt, taskType = 'simple', model = null) {
    const r = await api.post('/llm/generate', null, {
      params: { prompt, task_type: taskType, model, session_id: sessionId }
    })
    setDegraded(!!(r.data && r.data.degraded))
    return r
  },

  // Memory - Episodes
  storeEpisode(content, context = {}) {
    return api.post('/memory/episodes', null, {
      params: { content },
      data: context
    })
  },
  retrieveEpisodes(query, limit = 10) {
    return api.get('/memory/episodes', { params: { query, limit } })
  },

  // Memory - Facts
  storeFact(subject, predicate, object, confidence = 1.0) {
    return api.post('/memory/facts', null, {
      params: { subject, predicate, object, confidence }
    })
  },
  queryFacts(subject = null, predicate = null, object = null, limit = 10) {
    return api.get('/memory/facts', { params: { subject, predicate, object, limit } })
  },

  // Memory - Skills
  storeSkill(name, description, steps) {
    return api.post('/memory/skills', null, {
      params: { name, description, steps }
    })
  },
  listSkills() {
    return api.get('/memory/skills')
  },

  // Knowledge
  indexDocument(content, source) {
    return api.post('/knowledge/index', null, {
      params: { content, source }
    })
  },
  retrieveContext(query, topK = 5) {
    return api.get('/knowledge/retrieve', { params: { query, top_k: topK } })
  },
  async ragQuery(question, model = null) {
    const r = await api.post('/knowledge/rag', null, {
      params: { question, model, session_id: sessionId }
    })
    // Backend sets `degraded` when retrieval is down; Worker sets it on cloud failover.
    setDegraded(!!(r.data && r.data.degraded))
    return r
  },

  learn(text, source = null) {
    return api.post('/learn', { text, source })
  },

  useConnectors(prompt, maxSteps = 5) {
    return api.post('/connectors/query', null, {
      params: { prompt, max_steps: maxSteps }
    })
  },

  // Orchestrator
  runOrchestrator(goal, sid = sessionId) {
    return api.post('/orchestrator/run', null, {
      params: { goal, session_id: sid }
    })
  },

  // Conversations (durable history)
  listConversations(limit = 50) {
    return api.get('/conversations', { params: { limit } })
  },
  createConversation(title = null) {
    return api.post('/conversations', { title })
  },
  getConversation(id) {
    return api.get(`/conversations/${id}`)
  },
  renameConversation(id, title) {
    return api.patch(`/conversations/${id}`, { title })
  },
  deleteConversation(id) {
    return api.delete(`/conversations/${id}`)
  },
  appendMessages(id, messages) {
    return api.post(`/conversations/${id}/messages`, { messages })
  },

  // Host command execution (confirmation-gated)
  execStatus() {
    return api.get('/exec/status')
  },
  execPlan(task, os = 'Windows') {
    return api.post('/exec/plan', { task, os })
  },
  execRun(planId, index) {
    return api.post('/exec/run', { plan_id: planId, index })
  },
  execSummary(task, results) {
    return api.post('/exec/summary', { task, results })
  },

  // Streaming chat. onToken(text) is called per chunk; resolves with {conversationId, model}.
  // Uses fetch + ReadableStream to read Server-Sent Events (axios can't stream in-browser).
  async streamChat(message, { conversationId = null, taskType = 'simple', model = null, onToken, onMeta } = {}) {
    const resp = await fetch('/api/v1/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, conversation_id: conversationId, task_type: taskType, model })
    })
    if (!resp.ok || !resp.body) {
      throw new Error(`stream failed: HTTP ${resp.status}`)
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let convId = conversationId
    let usedModel = null
    let degradedSeen = false
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() // keep incomplete trailing chunk
      for (const block of lines) {
        const line = block.trim()
        if (!line.startsWith('data:')) continue
        const data = line.slice(5).trim()
        if (data === '[DONE]') continue
        let evt
        try { evt = JSON.parse(data) } catch { continue }
        if (evt.type === 'meta') { convId = evt.conversation_id; if (evt.degraded) degradedSeen = true; onMeta && onMeta(evt) }
        else if (evt.type === 'token') { onToken && onToken(evt.content) }
        else if (evt.type === 'done') { convId = evt.conversation_id || convId; usedModel = evt.model; if (evt.degraded) degradedSeen = true }
      }
    }
    // A clean local stream clears the banner; a cloud-failover stream raises it.
    setDegraded(degradedSeen)
    return { conversationId: convId, model: usedModel, degraded: degradedSeen }
  },

  // Autonomous build agent (ReAct loop, streamed). onEvent(evt) per step.
  async _streamBuild(url, body, onEvent) {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    if (!resp.ok || !resp.body) throw new Error(`build stream failed: HTTP ${resp.status}`)
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let sessionId = body.session_id || null
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop()
      for (const block of blocks) {
        const line = block.trim()
        if (!line.startsWith('data:')) continue
        const data = line.slice(5).trim()
        if (data === '[DONE]') continue
        let evt
        try { evt = JSON.parse(data) } catch { continue }
        if (evt.session_id) sessionId = evt.session_id
        onEvent && onEvent(evt)
      }
    }
    return { sessionId }
  },
  startBuild(goal, workdir = null, onEvent) {
    return this._streamBuild('/api/v1/build/run', { goal, workdir }, onEvent)
  },
  resumeBuild(sessionId, approve, onEvent) {
    return this._streamBuild('/api/v1/build/resume', { session_id: sessionId, approve }, onEvent)
  },
  continueBuild(sessionId, onEvent) {
    return this._streamBuild('/api/v1/build/continue', { session_id: sessionId }, onEvent)
  },
  cancelBuild(sessionId) {
    return api.post('/build/cancel', { session_id: sessionId, approve: false })
  },

  // System
  health() {
    return axios.get('/health')
  },
  deepHealth() {
    return api.get('/health/deep')
  },
  status() {
    return api.get('/status')
  }
}
