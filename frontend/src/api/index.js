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

  // Orchestrator
  runOrchestrator(goal, sid = sessionId) {
    return api.post('/orchestrator/run', null, {
      params: { goal, session_id: sid }
    })
  },

  // System
  health() {
    return axios.get('/health')
  },
  status() {
    return api.get('/status')
  }
}
