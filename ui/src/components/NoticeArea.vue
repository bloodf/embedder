<script setup lang="ts">
import { computed } from 'vue';
import Button from 'primevue/button';
import { OuiBanner } from '../../shared/src/components';
import { hourglass } from '../../shared/src/icons';
import { s, tracker, hello } from '../app/store';
import { splitLead } from '../app/logic';
import { t, fmt } from '../core/i18n';

const tone = { error: 'error', unknown: 'warn', success: 'success', info: 'info' } as const;
const split = (n: { id: number; kind: keyof typeof tone; text: string; at: number }) => ({ ...n, lead: splitLead(n.text) });
const lasting = computed(() => tracker.notices.filter(n => n.kind === 'error' || n.kind === 'unknown').map(split));
const passing = computed(() => tracker.notices.filter(n => n.kind === 'success' || n.kind === 'info').map(split));
// Loading a project has its own panel; every other command that is still out says so here.
const waiting = computed(() => [...tracker.pending.values()].filter(p => p.key !== 'load'));
</script>
<template>
  <section class="em-notices" :aria-label="t('msg.region')">
    <!-- Errors and unknown outcomes stay until dismissed and are announced at once. The two regions are the live
         regions (always rendered, so what is added later is announced); the banners in them carry no role of their own. -->
    <div role="alert" class="em-stack">
      <OuiBanner v-if="s.error" tone="error" role="none" :title="t('hello.failed')" data-test="hello-error">{{ s.error }}
        <template #actions><Button :label="t('common.retry')" severity="secondary" size="small" data-test="hello-retry" @click="hello" /></template>
      </OuiBanner>
      <OuiBanner v-for="n in lasting" :key="n.id" :tone="tone[n.kind]" role="none" :title="n.lead[0]">{{ n.lead[1] }} <span class="oui-meta">{{ fmt.time(n.at / 1000) }}</span>
        <template #actions><Button :label="t('common.dismiss')" severity="secondary" text size="small" @click="tracker.dismiss(n.id)" /></template>
      </OuiBanner>
    </div>
    <div role="status" aria-live="polite" class="em-stack">
      <OuiBanner v-for="p in waiting" :key="'p-' + p.key" tone="neutral" role="none" :icon="hourglass" :title="t('msg.waiting', { action: p.label })" />
      <OuiBanner v-for="n in passing" :key="n.id" :tone="tone[n.kind]" role="none" :title="n.lead[0]">{{ n.lead[1] }}
        <template #actions><Button :label="t('common.dismiss')" severity="secondary" text size="small" @click="tracker.dismiss(n.id)" /></template>
      </OuiBanner>
    </div>
  </section>
</template>
<style>
/* The live regions stay rendered so what is added later is announced; an empty one is taken out of the flow, so it
   opens no gap in the page grid. Not :empty, which Vue's empty anchor text nodes defeat. */
.em-notices { display: grid; gap: var(--oui-s3); min-width: 0; }
.em-stack { display: grid; gap: var(--oui-s2); }
.em-notices:not(:has(.oui-banner)), .em-stack:not(:has(> *)) { position: absolute; }
</style>
