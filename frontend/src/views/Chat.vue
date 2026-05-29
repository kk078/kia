<template>
  <div class="max-w-4xl mx-auto">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-3xl font-bold">
        <i class="fas fa-comments text-blue-500 mr-3"></i>
        Chat with Brain
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
          <p class="text-xl">Start a conversation with the Secondary Brain</p>
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
              <span class="text-sm font-semibold">{{ msg.role === 'user' ? 'You' : 'Brain' }}</span>
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
        <input
          v-model="input"
          @keyup.enter="sendMessage"
          :disabled="loading"
          type="text"
          placeholder="Type your message..."
          class="flex-1 bg-gray-700 text-white px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        />
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

  const userMessage = input.value.trim()
  messages.value.push({ role: 'user', content: userMessage })
  input.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const response = await api.generate(userMessage, taskType.value)
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
