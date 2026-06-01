import { ref } from 'vue'

// Global "cloud-failover / degraded" flag. Set true when a response indicates
// KIA is answering from the edge cloud fallback (local backend unreachable).
// App.vue renders a banner from this; the API layer flips it on chat/RAG/generate.
export const degraded = ref(false)

export function setDegraded(v) {
  degraded.value = !!v
}
