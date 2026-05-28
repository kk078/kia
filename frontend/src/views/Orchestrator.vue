<template>
  <div class="max-w-4xl mx-auto">
    <h1 class="text-3xl font-bold mb-6">
      <i class="fas fa-project-diagram text-blue-500 mr-3"></i>
      Orchestrator
    </h1>

    <div class="bg-gray-800 rounded-lg p-6 mb-6">
      <h2 class="text-2xl font-bold mb-4">Submit Complex Goal</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-semibold mb-2">Goal</label>
          <textarea
            v-model="goal"
            rows="4"
            placeholder="Describe your complex goal... The orchestrator will break it down into subtasks and execute them."
            class="w-full bg-gray-700 px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          ></textarea>
        </div>
        <div>
          <label class="block text-sm font-semibold mb-2">Session ID</label>
          <input
            v-model="sessionId"
            type="text"
            placeholder="default"
            class="w-full bg-gray-700 px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <button
          @click="runOrchestrator"
          :disabled="running"
          class="w-full bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-semibold disabled:opacity-50"
        >
          <i :class="running ? 'fas fa-spinner fa-spin' : 'fas fa-play'" class="mr-2"></i>
          {{ running ? 'Executing...' : 'Run Orchestrator' }}
        </button>
      </div>
    </div>

    <div v-if="result" class="bg-gray-800 rounded-lg p-6">
      <h2 class="text-2xl font-bold mb-4">
        <i class="fas fa-check-circle text-green-500 mr-2"></i>
        Result
      </h2>
      <div class="space-y-4">
        <div>
          <h3 class="font-semibold mb-2">Response</h3>
          <div class="bg-gray-700 p-4 rounded-lg whitespace-pre-wrap">
            {{ result.content }}
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <h3 class="font-semibold mb-2">Confidence</h3>
            <div class="bg-gray-700 p-4 rounded-lg">
              <div class="flex items-center justify-between mb-2">
                <span>{{ (result.confidence * 100).toFixed(0) }}%</span>
              </div>
              <div class="w-full bg-gray-600 rounded-full h-2">
                <div
                  class="bg-blue-600 h-2 rounded-full"
                  :style="{ width: `${result.confidence * 100}%` }"
                ></div>
              </div>
            </div>
          </div>
          <div>
            <h3 class="font-semibold mb-2">Sources</h3>
            <div class="bg-gray-700 p-4 rounded-lg">
              <ul class="list-disc list-inside space-y-1">
                <li v-for="(source, idx) in result.sources" :key="idx" class="text-sm">
                  {{ source }}
                </li>
              </ul>
            </div>
          </div>
        </div>
        <div v-if="result.metadata">
          <h3 class="font-semibold mb-2">Metadata</h3>
          <div class="bg-gray-700 p-4 rounded-lg">
            <pre class="text-sm overflow-x-auto">{{ JSON.stringify(result.metadata, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api'

const goal = ref('')
const sessionId = ref('default')
const running = ref(false)
const result = ref(null)

const runOrchestrator = async () => {
  if (!goal.value.trim()) return
  running.value = true
  result.value = null
  try {
    const response = await api.runOrchestrator(goal.value, sessionId.value || 'default')
    result.value = response.data
  } catch (error) {
    result.value = {
      content: `Error: ${error.response?.data?.detail || error.message}`,
      confidence: 0,
      sources: [],
      metadata: {}
    }
  } finally {
    running.value = false
  }
}
</script>
