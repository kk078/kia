import axios from 'axios'

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
  generate(prompt, taskType = 'simple', model = null) {
    return api.post('/llm/generate', null, {
      params: { prompt, task_type: taskType, model, session_id: sessionId }
    })
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
  ragQuery(question, model = null) {
    return api.post('/knowledge/rag', null, {
      params: { question, model, session_id: sessionId }
    })
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
        if (evt.type === 'meta') { convId = evt.conversation_id; onMeta && onMeta(evt) }
        else if (evt.type === 'token') { onToken && onToken(evt.content) }
        else if (evt.type === 'done') { convId = evt.conversation_id || convId; usedModel = evt.model }
      }
    }
    return { conversationId: convId, model: usedModel }
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
