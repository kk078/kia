<template>
  <div class="max-w-6xl mx-auto">
    <h1 class="text-3xl font-bold mb-6">
      <i class="fas fa-database text-blue-500 mr-3"></i>
      Memory Browser
    </h1>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
      <button
        @click="activeTab = 'episodes'"
        :class="activeTab === 'episodes' ? 'bg-blue-600' : 'bg-gray-800 hover:bg-gray-700'"
        class="p-6 rounded-lg transition-colors"
      >
        <i class="fas fa-film text-3xl mb-2"></i>
        <h3 class="text-xl font-bold">Episodes</h3>
        <p class="text-sm text-gray-400">Timestamped events</p>
      </button>
      <button
        @click="activeTab = 'facts'"
        :class="activeTab === 'facts' ? 'bg-blue-600' : 'bg-gray-800 hover:bg-gray-700'"
        class="p-6 rounded-lg transition-colors"
      >
        <i class="fas fa-lightbulb text-3xl mb-2"></i>
        <h3 class="text-xl font-bold">Facts</h3>
        <p class="text-sm text-gray-400">Knowledge graph</p>
      </button>
      <button
        @click="activeTab = 'skills'"
        :class="activeTab === 'skills' ? 'bg-blue-600' : 'bg-gray-800 hover:bg-gray-700'"
        class="p-6 rounded-lg transition-colors"
      >
        <i class="fas fa-tools text-3xl mb-2"></i>
        <h3 class="text-xl font-bold">Skills</h3>
        <p class="text-sm text-gray-400">Procedural memory</p>
      </button>
    </div>

    <!-- Episodes Tab -->
    <div v-if="activeTab === 'episodes'" class="bg-gray-800 rounded-lg p-6">
      <h2 class="text-2xl font-bold mb-4">Episodes</h2>
      <div class="mb-4 flex gap-2">
        <input
          v-model="episodeQuery"
          @keyup.enter="searchEpisodes"
          type="text"
          placeholder="Search episodes..."
          class="flex-1 bg-gray-700 px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button @click="searchEpisodes" class="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-lg">
          <i class="fas fa-search"></i>
        </button>
      </div>
      <div class="space-y-3">
        <div v-for="episode in episodes" :key="episode.id" class="bg-gray-700 p-4 rounded-lg">
          <div class="flex justify-between items-start mb-2">
            <span class="text-sm text-gray-400">{{ new Date(episode.timestamp).toLocaleString() }}</span>
            <span class="text-xs bg-blue-600 px-2 py-1 rounded">ID: {{ episode.id.substring(0, 8) }}</span>
          </div>
          <p class="mb-2">{{ episode.content }}</p>
          <div v-if="Object.keys(episode.context).length > 0" class="text-sm text-gray-400">
            <strong>Context:</strong> {{ JSON.stringify(episode.context) }}
          </div>
        </div>
        <div v-if="episodes.length === 0" class="text-center text-gray-500 py-8">
          No episodes found
        </div>
      </div>
    </div>

    <!-- Facts Tab -->
    <div v-if="activeTab === 'facts'" class="bg-gray-800 rounded-lg p-6">
      <h2 class="text-2xl font-bold mb-4">Facts</h2>
      <div class="mb-4 grid grid-cols-3 gap-2">
        <input v-model="factSubject" type="text" placeholder="Subject" class="bg-gray-700 px-4 py-2 rounded-lg" />
        <input v-model="factPredicate" type="text" placeholder="Predicate" class="bg-gray-700 px-4 py-2 rounded-lg" />
        <input v-model="factObject" type="text" placeholder="Object" class="bg-gray-700 px-4 py-2 rounded-lg" />
      </div>
      <button @click="queryFacts" class="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-lg mb-4">
        <i class="fas fa-search mr-2"></i>Query Facts
      </button>
      <div class="space-y-3">
        <div v-for="fact in facts" :key="fact.id" class="bg-gray-700 p-4 rounded-lg">
          <div class="flex items-center gap-2 mb-2">
            <span class="bg-green-600 px-3 py-1 rounded">{{ fact.subject }}</span>
            <i class="fas fa-arrow-right text-gray-500"></i>
            <span class="bg-yellow-600 px-3 py-1 rounded">{{ fact.predicate }}</span>
            <i class="fas fa-arrow-right text-gray-500"></i>
            <span class="bg-purple-600 px-3 py-1 rounded">{{ fact.object }}</span>
          </div>
          <div class="text-sm text-gray-400">
            Confidence: {{ (fact.confidence * 100).toFixed(0) }}%
          </div>
        </div>
        <div v-if="facts.length === 0" class="text-center text-gray-500 py-8">
          No facts found
        </div>
      </div>
    </div>

    <!-- Skills Tab -->
    <div v-if="activeTab === 'skills'" class="bg-gray-800 rounded-lg p-6">
      <h2 class="text-2xl font-bold mb-4">Skills</h2>
      <button @click="loadSkills" class="bg-blue-600 hover:bg-blue-700 px-6 py-2 rounded-lg mb-4">
        <i class="fas fa-sync mr-2"></i>Load Skills
      </button>
      <div class="space-y-3">
        <div v-for="skill in skills" :key="skill.id" class="bg-gray-700 p-4 rounded-lg">
          <h3 class="text-xl font-bold mb-2">{{ skill.name }}</h3>
          <p class="text-gray-400 mb-3">{{ skill.description }}</p>
          <div class="mb-2">
            <strong>Steps:</strong>
            <ol class="list-decimal list-inside ml-4 mt-1">
              <li v-for="(step, idx) in skill.steps" :key="idx">{{ step }}</li>
            </ol>
          </div>
          <div class="flex gap-4 text-sm text-gray-400">
            <span>Success Rate: {{ (skill.success_rate * 100).toFixed(0) }}%</span>
            <span>Usage Count: {{ skill.usage_count }}</span>
          </div>
        </div>
        <div v-if="skills.length === 0" class="text-center text-gray-500 py-8">
          No skills found
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api'

const activeTab = ref('episodes')

// Episodes
const episodeQuery = ref('')
const episodes = ref([])
const searchEpisodes = async () => {
  try {
    const response = await api.retrieveEpisodes(episodeQuery.value)
    episodes.value = response.data
  } catch (error) {
    console.error('Error searching episodes:', error)
  }
}

// Facts
const factSubject = ref('')
const factPredicate = ref('')
const factObject = ref('')
const facts = ref([])
const queryFacts = async () => {
  try {
    const response = await api.queryFacts(
      factSubject.value || null,
      factPredicate.value || null,
      factObject.value || null
    )
    facts.value = response.data
  } catch (error) {
    console.error('Error querying facts:', error)
  }
}

// Skills
const skills = ref([])
const loadSkills = async () => {
  try {
    const response = await api.listSkills()
    skills.value = response.data
  } catch (error) {
    console.error('Error loading skills:', error)
  }
}
</script>
