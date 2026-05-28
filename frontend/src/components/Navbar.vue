<template>
  <nav class="bg-gray-800 border-b border-gray-700">
    <div class="container mx-auto px-4">
      <div class="flex items-center justify-between h-16">
        <div class="flex items-center">
          <i class="fas fa-brain text-2xl text-blue-500 mr-3"></i>
          <span class="text-xl font-bold">Secondary Brain</span>
        </div>
        <div class="flex space-x-4">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="px-3 py-2 rounded-md text-sm font-medium transition-colors"
            :class="$route.path === item.path ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-700'"
          >
            <i :class="item.icon" class="mr-2"></i>
            {{ item.name }}
          </router-link>
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup>
const navItems = [
  { name: 'Chat', path: '/chat', icon: 'fas fa-comments' },
  { name: 'Memory', path: '/memory', icon: 'fas fa-database' },
  { name: 'Knowledge', path: '/knowledge', icon: 'fas fa-book' },
  { name: 'Orchestrator', path: '/orchestrator', icon: 'fas fa-project-diagram' },
  { name: 'Dashboard', path: '/dashboard', icon: 'fas fa-tachometer-alt' }
]
</script>
