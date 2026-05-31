<template>
  <div class="max-w-4xl mx-auto">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-3xl font-bold">
        <i class="fas fa-comments text-blue-500 mr-3"></i>
        Chat with KIA
      </h1>
      <button
        @click="newChat"
        class="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg text-sm transition-colors"
      >
        <i class="fas fa-plus mr-2"></i>New chat
      </button>
    </div>

    <div class="bg-gray-800 rounded-lg shadow-lg p-6 mb-4 h-[600px] flex flex-col">
      <div ref="messagesContainer" class="flex-1 overflow-y-auto mb-4 space-y-4">
        <div v-if="messages.length === 0" class="text-center text-gray-500 mt-20">
          <i class="fas fa-robot text-6xl mb-4"></i>
          <p class="text-xl">Start a conversation with KIA</p>
          <p class="text-sm mt-3 text-gray-600">
            Tip: <code>/learn &lt;text&gt;</code> teaches KIA new knowledge ·
            <code>/brain &lt;question&gt;</code> answers from memory ·
            <code>/use &lt;task&gt;</code> calls connectors (GitHub, web, Slack...)
          </p>
        </div>
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'"
        >
          <div
            :class="msg.role === 'user' ? 'bg-blue-600' : 'bg-gray-700'"
            class="rounded-lg px-4 py-3 max-w-[80%]"
          >
            <div class="flex items-center mb-1">
              <i :class="msg.role === 'user' ? 'fas fa-user' : 'fas fa-robot'" class="mr-2"></i>
              <span class="text-sm font-semibold">{{ msg.role === 'user' ? 'You' : 'KIA' }}</span>
            </div>
            <div class="whitespace-pre-wrap">{{ msg.content }}</div>
          </div>
        </div>
        <div v-if="loading" class="flex justify-start">
          <div class="bg-gray-700 rounded-lg px-4 py-3">
            <i class="fas fa-spinner fa-spin mr-2"></i>
            Thinking...
          </div>
        </div>
      </div>

      <div class="flex gap-2">
        <textarea
          v-model="input"
          @keydown.enter.exact.prevent="sendMessage"
          :disabled="loading"
          rows="2"
          placeholder="Message KIA...  (/learn teach · /brain ask memory · /use call connectors)"
          class="flex-1 bg-gray-700 text-white px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 resize-none"
        ></textarea>
        <button
          @click="sendMessage"
          :disabled="loading || !input.trim()"
          class="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <i class="fas fa-paper-plane"></i>
        </button>
      </div>
    </div>

    <div class="bg-gray-800 rounded-lg p-4">
      <h3 class="font-semibold mb-2">Task Type</h3>
      <div class="flex gap-2 flex-wrap">
        <button
          v-for="type in taskTypes"
          :key="type"
          @click="taskType = type"
          :class="taskType === type ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'"
          class="px-4 py-2 rounded-lg text-sm transition-colors"
        >
          {{ type }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import api from '../api'

const messages = ref([])
const input = ref('')
const loading = ref(false)
const taskType = ref('simple')
const messagesContainer = ref(null)

const taskTypes = ['simple', 'fast', 'planning', 'research', 'synthesis', 'code']

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

const sendMessage = async () => {
  if (!input.value.trim() || loading.value) return

  const text = input.value.trim()
  input.value = ''

  // /learn <text> : teach KIA (index to knowledge base now + queue for next fine-tune)
  if (text.toLowerCase().startsWith('/learn ')) {
    const body = text.slice(7).trim()
    messages.value.push({ role: 'user', content: '📚 Teaching KIA...' })
    loading.value = true
    scrollToBottom()
    try {
      const r = await api.learn(body)
      messages.value.push({
        role: 'assistant',
        content: `Learned ✓ - indexed ${r.data.chunks_indexed} chunk(s). Ask about it with /brain; it's queued for my next training.`
      })
    } catch (error) {
      messages.value.push({
        role: 'assistant',
        content: `Error: ${error.response?.data?.detail || error.message}`
      })
    } finally {
      loading.value = false
      scrollToBottom()
    }
    return
  }

  // /use <task> : answer using connected MCP tools (GitHub, web search, Slack, ...)
  if (text.toLowerCase().startsWith('/use ')) {
    const task = text.slice(5).trim()
    messages.value.push({ role: 'user', content: task })
    loading.value = true
    scrollToBottom()
    try {
      const r = await api.useConnectors(task)
      messages.value.push({
        role: 'assistant',
        content: r.data.answer + `\n\n_(via ${r.data.tools_available} connector tool(s))_`
      })
    } catch (error) {
      messages.value.push({
        role: 'assistant',
        content: `Error: ${error.response?.data?.detail || error.message}`
      })
    } finally {
      loading.value = false
      scrollToBottom()
    }
    return
  }

  // /brain <question> : answer using KIA's knowledge base (retrieval)
  if (text.toLowerCase().startsWith('/brain ')) {
    const q = text.slice(7).trim()
    messages.value.push({ role: 'user', content: q })
    loading.value = true
    scrollToBottom()
    try {
      const r = await api.ragQuery(q)
      messages.value.push({ role: 'assistant', content: r.data.answer })
    } catch (error) {
      messages.value.push({
        role: 'assistant',
        content: `Error: ${error.response?.data?.detail || error.message}`
      })
    } finally {
      loading.value = false
      scrollToBottom()
    }
    return
  }

  // normal chat
  messages.value.push({ role: 'user', content: text })
  loading.value = true
  scrollToBottom()
  try {
    const response = await api.generate(text, taskType.value)
    messages.value.push({ role: 'assistant', content: response.data.response })
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content: `Error: ${error.response?.data?.detail || error.message}`
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

const newChat = () => {
  messages.value = []
  input.value = ''
  api.newSession()
}
</script>
