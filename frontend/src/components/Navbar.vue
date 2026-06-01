<template>
  <nav class="kia-nav">
    <div class="mx-auto px-5" style="max-width:1100px">
      <div class="flex items-center justify-between" style="height:60px">
        <router-link to="/chat" class="no-underline">
          <KiaLogo :size="30" :wordmark="true" word-size="1.2rem" />
        </router-link>

        <div class="flex items-center" style="gap:.25rem">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="kia-navlink"
            :class="{ active: $route.path === item.path }"
          >
            <i :class="item.icon" style="font-size:.8rem"></i>
            <span class="hidden sm:inline">{{ item.name }}</span>
          </router-link>
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup>
import KiaLogo from './KiaLogo.vue'

const navItems = [
  { name: 'Chat', path: '/chat', icon: 'fas fa-comment' },
  { name: 'Memory', path: '/memory', icon: 'fas fa-layer-group' },
  { name: 'Knowledge', path: '/knowledge', icon: 'fas fa-book' },
  { name: 'Orchestrator', path: '/orchestrator', icon: 'fas fa-diagram-project' },
  { name: 'Dashboard', path: '/dashboard', icon: 'fas fa-gauge' }
]
</script>
