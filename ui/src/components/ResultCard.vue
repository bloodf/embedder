<script setup lang="ts">
import { computed } from 'vue';
import Button from 'primevue/button';
import Message from 'primevue/message';
import { OuiBanner, OuiIcon, OuiPanel, OuiReadout, OuiStatus } from '@orca-plugins/ui-foundation/src/components';
import { clipboard, external, file, pause, refresh, warning } from '@orca-plugins/ui-foundation/src/icons';
import { s, tracker, copyToClipboard } from '../app/store';
import { loadProject, openResult } from '../app/project';
import { t, tn, tMaybe, fmt, insertLabel } from '../core/i18n';

// The copy is named after the project it was made from: its file name (a time stamp and an id) and the folder it is
// kept in are storage details, shown only when OrcaSlicer could not open it and the user has to find the file.
const name = computed(() => s.project?.name || s.result?.name || '');
const said = computed(() => {
  const r = s.result;
  if (!r) return '';
  if (!r.pockets && r.removed) return tn('result.removedOnly', r.removed, { name: name.value });
  return [tn('result.added', r.pockets, { name: name.value }), r.removed ? tn('result.alsoRemoved', r.removed) : ''].filter(Boolean).join(' ');
});
type PauseItem = NonNullable<typeof s.result>['pauses'][number]['items'][number];
/** "2 pcs Ø6 × 3 mm disc (N up)": what goes in at a pause, in the page's words (the G-code comment is English). */
const itemText = (i: PauseItem) => tn('pause.item', i.n, { label: insertLabel(i.label) + (i.polarity ? ` (${t(`polarity.${i.polarity}`)})` : '') });
</script>

<!-- After Apply the job is over: the new copy is the project now, so the page offers to open it and asks for
     Load project again before any more pockets (a second Apply on the old copy would drop the first one's). -->
<template>
  <section v-if="s.result" class="em-result" data-test="result" :aria-label="t('result.title')">
    <OuiBanner tone="success" :title="t('result.title')" data-test="result-banner" dismissible :dismiss-key="'result:' + s.applies + ':' + s.result.path" :close-label="t('common.close')"><span>{{ said }}</span></OuiBanner>

    <OuiPanel :title="name" :icon="file" :meta="t('result.meta', { time: fmt.time(s.applies / 1000) })" flush>
      <!-- What to do at the printer is the main line: where the print stops and what goes in. -->
      <div v-if="s.result.pauses.length" class="oui-hero em-result-pauses" data-test="result-pauses">
        <OuiReadout v-for="p in s.result.pauses" :key="p.top_z" :icon="pause" :label="t('plan.pause')" :value="'Z ' + fmt.number(p.top_z, 2)" unit="mm" size="lg" :sub="p.items.map(itemText).join(', ')" />
      </div>
      <div class="em-result-body">
        <Message v-for="w in s.result.warnings" :key="w" severity="warn" size="small">
          <template #icon><OuiIcon :icon="warning" :size="14" /></template>{{ tMaybe(`warn.${w}`, w) }}
        </Message>
        <p class="oui-meta" data-test="result-copy">{{ t('result.copy') }}</p>
        <p class="oui-meta" data-test="result-next">{{ t('result.next') }}</p>
        <p v-if="s.result.pruned" class="oui-meta" data-test="result-pruned">{{ tn('result.pruned', s.result.pruned) }}</p>
      </div>
      <template #footer>
        <Button :label="t('result.open')" :loading="tracker.isBusy('open')" data-test="open" @click="openResult"><template #icon><OuiIcon :icon="external" :size="14" /></template></Button>
        <Button :label="t('load.again')" severity="secondary" :disabled="!!s.loading" data-test="result-reload" @click="loadProject"><template #icon><OuiIcon :icon="refresh" :size="14" /></template></Button>
        <span role="status" class="em-result-opened">
          <OuiStatus v-if="s.opened" :state="s.opened === 'asked' ? 'pending' : 'warn'" variant="plain" data-test="opened">{{ t(s.opened === 'asked' ? 'result.asked' : 'result.none') }}</OuiStatus>
        </span>
        <!-- Only when OrcaSlicer could not be asked: now the user has to find the file, so here is where it is. -->
        <div v-if="s.opened === 'none'" class="oui-well em-result-path">
          <code class="oui-mono" data-test="result-path">{{ s.result.path }}</code>
          <Button :label="t('result.copyPath')" severity="secondary" text size="small" data-test="copy-path" @click="copyToClipboard(s.result.path)"><template #icon><OuiIcon :icon="clipboard" :size="14" /></template></Button>
        </div>
      </template>
    </OuiPanel>
  </section>
</template>

<style>
.em-result { display: grid; gap: var(--oui-s3); width: min(100%, 880px); margin-top: var(--oui-s4); }
.em-result-pauses { display: flex; flex-wrap: wrap; gap: var(--oui-s4) var(--oui-s8); margin: var(--oui-s4) var(--oui-s4) 0; }
.em-result-body { display: grid; gap: var(--oui-s2); padding: var(--oui-s4); }
.em-result-opened { flex: 1 1 200px; min-width: 0; }
.em-result-opened .oui-status { white-space: normal; }
.em-result-path { flex: 1 1 100%; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--oui-s2); min-width: 0; padding: var(--oui-s2) var(--oui-s3); }
.em-result-path > code { flex: 1 1 240px; min-width: 0; overflow-wrap: anywhere; font-size: var(--oui-text-sm); user-select: all; -webkit-user-select: all; }
</style>
