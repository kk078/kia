<template>
  <div class="max-w-6xl mx-auto">
    <h1 class="text-3xl font-bold mb-6">
      <i class="fas fa-book text-blue-500 mr-3"></i>
      Knowledge Base
    </h1>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Index Document -->
      <div class="bg-gray-800 rounded-lg p-6">
        <h2 class="text-2xl font-bold mb-4">
          <i class="fas fa-plus-circle text-green-500 mr-2"></i>
          Index Document
        </h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-semibold mb-2">Source</label>
            <input
              v-model="docSource"
              type="text"
              placeholder="e.g., manual, file.txt"
              class="w-full bg-gray-700 px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label class="block text-sm font-semibold mb-2">Content</label>
            <textarea
              v-model="docContent"
              rows="8"
              placeholder="Enter document content..."
              class="w-full bg-gray-700 px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            ></textarea>
          </div>
          <button
            @click="indexDocument"
            :disabled="indexing"
            class="w-full bg-green-600 hover:bg-green-700 px-6 py-3 rounded-lg font-semibold disabled:opacity-50"
          >
            <i :class="indexing ? 'fas fa-spinner fa-spin' : 'fas fa-upload'" class="mr-2"></i>
            {{ indexing ? 'Indexing...' : 'Index Document' }}
          </button>
          <div v-if="indexResult" class="mt-4 p-4 bg-gray-700 rounded-lg">
            <p class="text-green-400">
              <i class="fas fa-check-circle mr-2"></i>
              Indexed {{ indexResult.chunk_ids?.length || 0 }} chunks
            </p>
          </div>
        </div>
      </div>

      <!-- RAG Query -->
      <div class="bg-gray-800 rounded-lg p-6">
        <h2 class="text-2xl font-bold mb-4">
          <i class="fas fa-search text-blue-500 mr-2"></i>
          RAG Query
        </h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-semibold mb-2">Question</label>
            <textarea
              v-model="ragQuestion"
              rows="4"
              placeholder="Ask a question about your knowledge base..."
              class="w-full bg-gray-700 px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            ></textarea>
          </div>
          <button
            @click="queryRAG"
            :disabled="querying"
            class="w-full bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-semibold disabled:opacity-50"
          >
            <i :class="querying ? 'fas fa-spinner fa-spin' : 'fas fa-magic'" class="mr-2"></i>
            {{ querying ? 'Querying...' : 'Ask Question' }}
          </button>
          <div v-if="ragAnswer" class="mt-4 p-4 bg-gray-700 rounded-lg">
            <h3 class="font-semibold mb-2">Answer:</h3>
            <p class="whitespace-pre-wrap">{{ ragAnswer }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Context Retrieval -->
    <div class="bg-gray-800 rounded-lg p-6 mt-6">
      <h2 class="text-2xl font-bold mb-4">
        <i class="fas fa-layer-group text-purple-500 mr-2"></i>
        Context Retrieval
      </h2>
      <div class="flex gap-2 mb-4">
        <input
          v-model="contextQuery"
          @keyup.enter="retrieveContext"
          type="text"
          placeholder="Search for relevant context..."
          class="flex-1 bg-gray-700 px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button @click="retrieveContext" class="bg-purple-600 hover:bg-purple-700 px-6 py-2 rounded-lg">
          <i class="fas fa-search"></i>
        </button>
      </div>
      <div class="space-y-3">
        <div v-for="(chunk, idx) in contextChunks" :key="idx" class="bg-gray-700 p-4 rounded-lg">
          <div class="flex justify-between items-start mb-2">
            <span class="text-sm text-gray-400">Document: {{ chunk.document_id }}</span>
            <span class="text-xs bg-purple-600 px-2 py-1 rounded">Chunk {{ idx + 1 }}</span>
          </div>
          <p class="text-sm">{{ chunk.content }}</p>
        </div>
        <div v-if="contextChunks.length === 0 && contextQuery" class="text-center text-gray-500 py-8">
          No context found
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api'

// Index Document
const docSource = ref('')
const docContent = ref('')
const indexing = ref(false)
const indexResult = ref(null)
const indexDocument = async () => {
  if (!docContent.value.trim()) return
  indexing.value = true
  try {
    const response = await api.indexDocument(docContent.value, docSource.value || 'manual')
    indexResult.value = response.data
    docContent.value = ''
    docSource.value = ''
  } catch (error) {
    console.error('Error indexing document:', error)
  } finally {
    indexing.value = false
  }
}

// RAG Query
const ragQuestion = ref('')
const querying = ref(false)
const ragAnswer = ref('')
const queryRAG = async () => {
  if (!ragQuestion.value.trim()) return
  querying.value = true
  ragAnswer.value = ''
  try {
    const response = await api.ragQuery(ragQuestion.value)
    ragAnswer.value = response.data.answer
  } catch (error) {
    ragAnswer.value = `Error: ${error.response?.data?.detail || error.message}`
  } finally {
    querying.value = false
  }
}

// Context Retrieval
const contextQuery = ref('')
const contextChunks = ref([])
const retrieveContext = async () => {
  if (!contextQuery.value.trim()) return
  try {
    const response = await api.retrieveContext(contextQuery.value)
    contextChunks.value = response.data
  } catch (error) {
    console.error('Error retrieving context:', error)
  }
}
</script>
