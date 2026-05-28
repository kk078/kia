<template>
  <div class="max-w-6xl mx-auto">
    <h1 class="text-3xl font-bold mb-6">
      <i class="fas fa-tachometer-alt text-blue-500 mr-3"></i>
      System Dashboard
    </h1>

    <!-- Health Status -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <div
        v-for="service in services"
        :key="service.name"
        class="bg-gray-800 rounded-lg p-6"
      >
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-lg font-bold">{{ service.name }}</h3>
          <i
            :class="service.healthy ? 'fas fa-check-circle text-green-500' : 'fas fa-times-circle text-red-500'"
            class="text-2xl"
          ></i>
        </div>
        <p class="text-sm text-gray-400">{{ service.url }}</p>
        <p :class="service.healthy ? 'text-green-400' : 'text-red-400'" class="text-sm font-semibold mt-2">
          {{ service.healthy ? 'Healthy' : 'Unhealthy' }}
        </p>
      </div>
    </div>

    <!-- System Info -->
    <div class="bg-gray-800 rounded-lg p-6 mb-6">
      <h2 class="text-2xl font-bold mb-4">System Information</h2>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <p class="text-gray-400 text-sm">Version</p>
          <p class="text-xl font-bold">{{ status.version }}</p>
        </div>
        <div>
          <p class="text-gray-400 text-sm">Environment</p>
          <p class="text-xl font-bold">{{ status.environment }}</p>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="bg-gray-800 rounded-lg p-6">
      <h2 class="text-2xl font-bold mb-4">Quick Actions</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <button
          @click="refreshStatus"
          class="bg-blue-600 hover:bg-blue-700 p-4 rounded-lg transition-colors"
        >
          <i class="fas fa-sync text-2xl mb-2"></i>
          <p class="text-sm">Refresh Status</p>
        </button>
        <router-link
          to="/chat"
          class="bg-green-600 hover:bg-green-700 p-4 rounded-lg transition-colors text-center"
        >
          <i class="fas fa-comments text-2xl mb-2"></i>
          <p class="text-sm">Start Chat</p>
        </router-link>
        <router-link
          to="/memory"
          class="bg-purple-600 hover:bg-purple-700 p-4 rounded-lg transition-colors text-center"
        >
          <i class="fas fa-database text-2xl mb-2"></i>
          <p class="text-sm">Browse Memory</p>
        </router-link>
        <router-link
          to="/knowledge"
          class="bg-yellow-600 hover:bg-yellow-700 p-4 rounded-lg transition-colors text-center"
        >
          <i class="fas fa-book text-2xl mb-2"></i>
          <p class="text-sm">Knowledge Base</p>
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const services = ref([
  { name: 'API', url: 'localhost:8000', healthy: false },
  { name: 'Redis', url: 'localhost:6379', healthy: false },
  { name: 'Weaviate', url: 'localhost:8081', healthy: false },
  { name: 'FalkorDB', url: 'localhost:6380', healthy: false }
])

const status = ref({
  version: '0.1.0',
  environment: 'development'
})

const refreshStatus = async () => {
  try {
    const healthResponse = await api.health()
    services.value[0].healthy = healthResponse.data.status === 'healthy'

    const statusResponse = await api.status()
    status.value = statusResponse.data
    services.value[1].healthy = true
    services.value[2].healthy = true
    services.value[3].healthy = true
  } catch (error) {
    console.error('Error refreshing status:', error)
    services.value[0].healthy = false
  }
}

onMounted(() => {
  refreshStatus()
})
</script>
