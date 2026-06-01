<template>
  <div class="mx-auto" style="max-width:980px">
    <h1 style="font-size:1.9rem;font-weight:700;margin-bottom:.25rem">Memory</h1>
    <p style="color:var(--text-2);font-size:.9rem;margin-bottom:1.5rem">Episodes, facts, and skills KIA remembers</p>

    <!-- Segmented tab control -->
    <div class="kia-segment" style="margin-bottom:1.25rem">
      <button :class="{active: activeTab==='episodes'}" @click="activeTab='episodes'">
        <i class="fas fa-film" style="margin-right:.4rem"></i>Episodes</button>
      <button :class="{active: activeTab==='facts'}" @click="activeTab='facts'">
        <i class="fas fa-diagram-project" style="margin-right:.4rem"></i>Facts</button>
      <button :class="{active: activeTab==='skills'}" @click="activeTab='skills'">
        <i class="fas fa-screwdriver-wrench" style="margin-right:.4rem"></i>Skills</button>
    </div>

    <!-- Episodes -->
    <div v-if="activeTab==='episodes'" class="kia-card" style="padding:1.5rem">
      <div class="flex gap-2 mb-4">
        <input v-model="episodeQuery" @keyup.enter="searchEpisodes" type="text" placeholder="Search episodes…" class="kia-input" />
        <button @click="searchEpisodes" class="kia-btn"><i class="fas fa-magnifying-glass"></i></button>
      </div>
      <div class="space-y-3">
        <div v-for="episode in episodes" :key="episode.id" class="kia-rise" style="background:var(--surface-2);border:1px solid var(--hairline);border-radius:14px;padding:1rem">
          <div class="flex justify-between items-start mb-1.5">
            <span style="font-size:.8rem;color:var(--text-3)">{{ new Date(episode.timestamp).toLocaleString() }}</span>
            <span style="font-size:.72rem;background:var(--fill);color:var(--text-2);padding:.15rem .5rem;border-radius:980px">{{ episode.id.substring(0,8) }}</span>
          </div>
          <p style="font-size:.95rem">{{ episode.content }}</p>
          <div v-if="Object.keys(episode.context||{}).length" style="font-size:.82rem;color:var(--text-2);margin-top:.5rem">
            <strong>Context:</strong> {{ JSON.stringify(episode.context) }}
          </div>
        </div>
        <p v-if="episodes.length===0" style="text-align:center;color:var(--text-3);padding:2rem 0">No episodes found</p>
      </div>
    </div>

    <!-- Facts -->
    <div v-if="activeTab==='facts'" class="kia-card" style="padding:1.5rem">
      <div class="grid mb-3" style="grid-template-columns:1fr 1fr 1fr;gap:.5rem">
        <input v-model="factSubject" placeholder="Subject" class="kia-input" />
        <input v-model="factPredicate" placeholder="Predicate" class="kia-input" />
        <input v-model="factObject" placeholder="Object" class="kia-input" />
      </div>
      <button @click="queryFacts" class="kia-btn mb-4"><i class="fas fa-magnifying-glass"></i> Query facts</button>
      <div class="space-y-3">
        <div v-for="fact in facts" :key="fact.id" class="kia-rise" style="background:var(--surface-2);border:1px solid var(--hairline);border-radius:14px;padding:1rem">
          <div class="flex items-center flex-wrap gap-2 mb-1.5">
            <span class="kia-chip" style="background:rgba(52,199,89,.14);color:#1a7f37">{{ fact.subject }}</span>
            <i class="fas fa-arrow-right" style="color:var(--text-3);font-size:.75rem"></i>
            <span class="kia-chip" style="background:rgba(255,149,0,.16);color:#9a5b00">{{ fact.predicate }}</span>
            <i class="fas fa-arrow-right" style="color:var(--text-3);font-size:.75rem"></i>
            <span class="kia-chip" style="background:rgba(94,92,230,.14);color:#4b49c4">{{ fact.object }}</span>
          </div>
          <div style="font-size:.8rem;color:var(--text-2)">Confidence {{ (fact.confidence*100).toFixed(0) }}%</div>
        </div>
        <p v-if="facts.length===0" style="text-align:center;color:var(--text-3);padding:2rem 0">No facts found</p>
      </div>
    </div>

    <!-- Skills -->
    <div v-if="activeTab==='skills'" class="kia-card" style="padding:1.5rem">
      <button @click="loadSkills" class="kia-btn mb-4"><i class="fas fa-rotate"></i> Load skills</button>
      <div class="space-y-3">
        <div v-for="skill in skills" :key="skill.id" class="kia-rise" style="background:var(--surface-2);border:1px solid var(--hairline);border-radius:14px;padding:1rem">
          <h3 style="font-size:1.1rem;font-weight:600;margin-bottom:.25rem">{{ skill.name }}</h3>
          <p style="color:var(--text-2);font-size:.9rem;margin-bottom:.6rem">{{ skill.description }}</p>
          <ol style="list-style:decimal;margin-left:1.2rem;font-size:.9rem">
            <li v-for="(step,i) in skill.steps" :key="i" style="margin-bottom:.15rem">{{ step }}</li>
          </ol>
          <div class="flex gap-4" style="font-size:.8rem;color:var(--text-2);margin-top:.6rem">
            <span>Success {{ (skill.success_rate*100).toFixed(0) }}%</span>
            <span>Used {{ skill.usage_count }}×</span>
          </div>
        </div>
        <p v-if="skills.length===0" style="text-align:center;color:var(--text-3);padding:2rem 0">No skills found</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api'

const activeTab = ref('episodes')
const episodeQuery = ref(''); const episodes = ref([])
const searchEpisodes = async () => { try { episodes.value = (await api.retrieveEpisodes(episodeQuery.value)).data } catch(e){ console.error(e) } }
const factSubject = ref(''); const factPredicate = ref(''); const factObject = ref(''); const facts = ref([])
const queryFacts = async () => { try { facts.value = (await api.queryFacts(factSubject.value||null, factPredicate.value||null, factObject.value||null)).data } catch(e){ console.error(e) } }
const skills = ref([])
const loadSkills = async () => { try { skills.value = (await api.listSkills()).data } catch(e){ console.error(e) } }
</script>

<style scoped>
.kia-chip { padding:.25rem .7rem; border-radius:980px; font-size:.85rem; font-weight:500; }
</style>
