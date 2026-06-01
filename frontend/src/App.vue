<template>
  <div style="min-height:100vh;background:var(--bg)">
    <Navbar />
    <main class="mx-auto px-5 py-8" style="max-width:1100px">
      <router-view v-slot="{ Component }">
        <transition name="kia-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import Navbar from './components/Navbar.vue'
</script>

<style>
.kia-fade-enter-active, .kia-fade-leave-active { transition: opacity .18s ease, transform .18s ease; }
.kia-fade-enter-from { opacity: 0; transform: translateY(4px); }
.kia-fade-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
