<script setup lang="ts">
import { reactive, watchEffect } from 'vue';
import type { Pending } from '../core/tracker';
import Button from 'primevue/button';
import { OuiBanner } from '../../shared/src/components';
import { hourglass } from '../../shared/src/icons';
import { s, tracker, hello } from '../app/store';
import { t } from '../core/i18n';

// What the commands said (done, failed, no answer) is in the toasts. Here: the states that last while they hold, the
// plugin not answering and a command still out (loading a project has its own panel). Each can be closed; it comes
// back when the state changes (another error, another command sent): each banner is bound to its condition (:show),
// so when it clears the close is forgotten. A command's banner therefore stays mounted after the answer, hidden, with
// the last send it was about.
const waiting = reactive(new Map<string, Pending>());
watchEffect(() => { for (const p of tracker.pending.values()) if (p.key !== 'load') waiting.set(p.key, p); });
</script>
<template>
  <section class="em-notices" :aria-label="t('msg.region')">
    <!-- The two regions are the live regions (always rendered, so what is added later is announced); the banners in
         them carry no role of their own. -->
    <div role="alert" class="em-stack">
      <OuiBanner :show="!!s.error" tone="error" role="none" :title="t('hello.failed')" data-test="hello-error"
        dismissible :dismiss-key="'hello:' + s.helloFails + ':' + s.error" :close-label="t('common.close')">{{ s.error }}
        <template #actions><Button :label="t('common.retry')" severity="secondary" size="small" data-test="hello-retry" @click="hello" /></template>
      </OuiBanner>
    </div>
    <div role="status" aria-live="polite" class="em-stack">
      <OuiBanner v-for="[k, p] in waiting" :key="'p-' + k" :show="tracker.pending.has(k)" tone="neutral" role="none" :icon="hourglass" :title="t('msg.waiting', { action: p.label })"
        data-test="waiting" dismissible :dismiss-key="'waiting:' + p.key + ':' + p.startedAt" :close-label="t('common.close')" />
    </div>
  </section>
</template>
<style>
/* The live regions stay rendered, in the flow, so what is added later is announced. An empty one takes no height, and
   with no banner at all the page drops the gap it would open above the content. Not :empty, which Vue's empty anchor
   text nodes defeat. */
.em-notices { display: grid; min-width: 0; }
.em-stack { display: grid; gap: var(--oui-s2); }
.em-stack:not(:has(> *)) { height: 0; overflow: hidden; }
.em-stack:has(> *) + .em-stack:has(> *) { margin-top: var(--oui-s2); }
.em:not(:has(> .em-notices .oui-banner)) { row-gap: 0; }   /* :has cannot nest */
</style>
