<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ name: string; size?: number }>(), { size: 36 })

// Stable colour per name so a player keeps the same avatar in the lobby,
// the leaderboard and the podium.
const hue = computed(() => {
  let hash = 0
  for (const char of props.name) hash = (hash * 31 + char.codePointAt(0)!) % 360
  return hash
})
const initial = computed(() => (props.name.trim()[0] ?? '?').toUpperCase())
</script>

<template>
  <span
    class="avatar"
    :style="{
      width: size + 'px',
      height: size + 'px',
      fontSize: size * 0.42 + 'px',
      background: `linear-gradient(135deg, hsl(${hue} 70% 52%), hsl(${(hue + 40) % 360} 70% 42%))`,
    }"
    aria-hidden="true"
  >
    {{ initial }}
  </span>
</template>

<style scoped>
.avatar {
  display: inline-grid;
  place-items: center;
  flex: none;
  border-radius: 50%;
  color: #fff;
  font-weight: 800;
  box-shadow: 0 2px 6px rgba(23, 31, 72, 0.25);
}
</style>
