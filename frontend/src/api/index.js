import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json'
  }
})

export default {
  // LLM
  generate(prompt, taskType = 'simple', model = null) {
    return api.post('/llm/generate', null, {
      params: { prompt, task_type: taskType, model }
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
      params: { question, model }
    })
  },

  // Orchestrator
  runOrchestrator(goal, sessionId = 'default') {
    return api.post('/orchestrator/run', null, {
      params: { goal, session_id: sessionId }
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
