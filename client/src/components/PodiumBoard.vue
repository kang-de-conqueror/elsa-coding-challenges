<script setup lang="ts">
import { computed } from 'vue'
import { useQuizStore } from '@/stores/quiz'
import UserAvatar from '@/components/UserAvatar.vue'

const store = useQuizStore()

const MEDALS = ['🥇', '🥈', '🥉']
// Visual order on a podium is 2nd, 1st, 3rd.
const podium = computed(() => {
  const top = store.leaderboard.slice(0, 3)
  return [top[1], top[0], top[2]].filter((entry) => entry !== undefined)
})
</script>

<template>
  <div v-if="podium.length" class="podium" aria-label="Top players">
    <div v-for="entry in podium" :key="entry.user_id" class="place" :class="'p' + entry.rank">
      <span class="medal" aria-hidden="true">{{ MEDALS[entry.rank - 1] }}</span>
      <UserAvatar :name="entry.username" :size="entry.rank === 1 ? 64 : 52" />
      <strong class="who">{{ entry.username }}</strong>
      <span class="pts">{{ entry.score }} pts</span>
      <div class="block">#{{ entry.rank }}</div>
    </div>
  </div>
</template>

<style scoped>
.podium {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 0.75rem;
  padding: 1rem 0 0;
}
.place {
  display: grid;
  justify-items: center;
  gap: 0.25rem;
  width: min(9rem, 30%);
}
.medal {
  font-size: 1.8rem;
  animation: pop 0.6s ease both;
}
.who {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pts {
  font-size: 0.85rem;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}
.block {
  width: 100%;
  margin-top: 0.4rem;
  display: grid;
  place-items: center;
  border-radius: 14px 14px 0 0;
  color: #fff;
  font-weight: 900;
  font-size: 1.4rem;
  animation: rise 0.7s ease both;
}
.p1 .block {
  height: 8rem;
  background: linear-gradient(180deg, var(--gold), #d99a00);
}
.p2 .block {
  height: 6rem;
  background: linear-gradient(180deg, var(--silver), #7d879b);
}
.p3 .block {
  height: 4.5rem;
  background: linear-gradient(180deg, var(--bronze), #a2621f);
}
@keyframes rise {
  from {
    transform: scaleY(0);
    transform-origin: bottom;
  }
  to {
    transform: scaleY(1);
    transform-origin: bottom;
  }
}
@keyframes pop {
  0% {
    transform: scale(0);
  }
  70% {
    transform: scale(1.25);
  }
  100% {
    transform: scale(1);
  }
}
</style>
