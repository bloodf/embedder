<script setup lang="ts">
import { reactive, ref, watch, watchEffect } from 'vue';
import type { Pending } from '../core/tracker';
import Button from 'primevue/button';
import { OuiBanner, OuiIcon } from '@orca-plugins/ui-foundation/src/components';
import { chevronDown, chevronRight, clipboard, hourglass } from '@orca-plugins/ui-foundation/src/icons';
import { s, tracker, hello, copyToClipboard } from '../app/store';
import { t } from '../core/i18n';

// What the commands said (done, failed, no answer) is in the toasts. Here: the states that last while they hold, the
// plugin not answering and a command that is taking long (loading a project has its own panel). A command's banner can
// be closed; it comes back when the state changes (another command sent): each banner is bound to its condition
// (:show), so when it clears the close is forgotten. It therefore stays mounted after the answer, hidden, with the
// last send it was about.
//
// A command is only said to be still working once it has been out for SLOW_MS: nearly all answer within a frame or
// two, and a banner that comes and goes that fast only makes the page jump. Reads and saves the user did not ask for
// by name (the preset list, the copies check, a setting kept) are never announced.
const SLOW_MS = 600;
const waiting = reactive(new Map<string, Pending>());
const slow = reactive(new Set<string>());
watchEffect(() => {
  for (const p of tracker.pending.values()) {
    if (p.key === 'load' || p.background || waiting.get(p.key) === p) continue;
    waiting.set(p.key, p);
    slow.delete(p.key);
    setTimeout(() => { if (tracker.pending.get(p.key) === p) slow.add(p.key); }, SLOW_MS);
  }
});
// The technical text behind "could not start" stays closed until asked for.
const tech = ref(false);
watch(() => s.errorDetail, () => { tech.value = false; });
</script>
<template>
  <section class="em-notices" :aria-label="t('msg.region')">
    <!-- The two regions are the live regions (always rendered, so what is added later is announced); the banners in
         them carry no role of their own. -->
    <div role="alert" class="em-stack">
      <!-- Not dismissible: while it holds, Load project is off and points here. -->
      <OuiBanner id="em-hello-error" :show="!!s.error" tone="error" role="none" :title="t('hello.failed')" data-test="hello-error">{{ t('hello.hint') }}
        <template #actions>
          <Button v-if="s.errorDetail" text severity="secondary" size="small" :aria-expanded="tech" aria-controls="em-hello-detail" data-test="hello-details" @click="tech = !tech">
            <template #icon><OuiIcon :icon="tech ? chevronDown : chevronRight" :size="14" /></template>{{ t('err.details') }}</Button>
          <Button :label="t('common.retry')" severity="secondary" size="small" data-test="hello-retry" @click="hello" />
        </template>
      </OuiBanner>
      <div v-if="s.error && s.errorDetail" v-show="tech" id="em-hello-detail" class="oui-well em-tech" data-test="hello-detail">
        <code class="oui-error-detail">{{ s.errorDetail }}</code>
        <Button :label="t('err.copyDetails')" severity="secondary" text size="small" @click="copyToClipboard(s.errorDetail)"><template #icon><OuiIcon :icon="clipboard" :size="14" /></template></Button>
      </div>
    </div>
    <div role="status" aria-live="polite" class="em-stack">
      <OuiBanner v-for="[k, p] in waiting" :key="'p-' + k" :show="tracker.pending.get(k) === p && slow.has(k)" tone="neutral" role="none" :icon="hourglass" :title="t('msg.waiting', { action: p.label })"
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
.em-tech { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: var(--oui-s2); padding: var(--oui-s2) var(--oui-s3); }
.em-tech > code { flex: 1 1 240px; min-width: 0; padding-block: 4px; user-select: text; -webkit-user-select: text; }
</style>
