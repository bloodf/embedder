<script setup lang="ts">
import { computed } from 'vue';
import Button from 'primevue/button';
import Message from 'primevue/message';
import { OuiBanner, OuiIcon, OuiReadout, OuiSavedCopy } from '@orca-plugins/ui-foundation/src/components';
import { pause, refresh, warning } from '@orca-plugins/ui-foundation/src/icons';
import { s, tracker } from '../app/store';
import { loadProject, openResult } from '../app/project';
import { t, tn, tMaybe, fmt, insertLabel } from '../core/i18n';

// The copy is named after the project it was made from: its file name (a time stamp and an id) and the folder it is
// kept in are storage details. The shared card shows the path only when OrcaSlicer could not open the copy and the
// user has to find the file.
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
const labels = computed(() => ({ heading: t('result.heading'), open: t('result.open'), copyPath: t('result.copyPath'), copied: t('common.copied'), path: t('result.pathLabel') }));
</script>

<!-- After Apply the job is over: the new copy is the project now, so the page offers to open it and asks for
     Load project again before any more pockets (a second Apply on the old copy would drop the first one's). -->
<template>
  <section v-if="s.result" class="em-result" data-test="result" :aria-label="t('result.title')">
    <OuiBanner tone="success" :title="t('result.title')" data-test="result-banner" dismissible :dismiss-key="'result:' + s.applies + ':' + s.result.path" :close-label="t('common.close')"><span>{{ said }}</span></OuiBanner>

    <!-- What to do at the printer is the main line: where the print stops and what goes in. -->
    <div v-if="s.result.pauses.length" class="oui-hero em-result-pauses" data-test="result-pauses">
      <OuiReadout v-for="p in s.result.pauses" :key="p.top_z" :icon="pause" :label="t('plan.pause')" :value="'Z ' + fmt.number(p.top_z, 2)" unit="mm" size="lg" :sub="p.items.map(itemText).join(', ')" />
    </div>
    <Message v-for="w in s.result.warnings" :key="w" severity="warn" size="small">
      <template #icon><OuiIcon :icon="warning" :size="14" /></template>{{ tMaybe(`warn.${w}`, w) }}
    </Message>

    <OuiSavedCopy :title="name" :meta="t('result.meta', { time: fmt.time(s.applies / 1000) })" :file="s.result.name" :path="s.result.path" :labels="labels"
                  :failed="s.opened === 'none'" :status="s.opened ? t(s.opened === 'asked' ? 'result.asked' : 'result.none') : undefined" :opening="tracker.isBusy('open')" @open="openResult">
      <template #actions>
        <Button :label="t('load.again')" severity="secondary" :disabled="!!s.loading" data-test="result-reload" @click="loadProject"><template #icon><OuiIcon :icon="refresh" :size="14" /></template></Button>
      </template>
      <p data-test="result-copy">{{ t('result.copy') }}</p>
      <p data-test="result-next">{{ t('result.next') }}</p>
      <p v-if="s.result.pruned" data-test="result-pruned">{{ tn('result.pruned', s.result.pruned) }}</p>
    </OuiSavedCopy>
  </section>
</template>

<style>
.em-result { display: grid; gap: var(--oui-s3); width: min(100%, 880px); margin-top: var(--oui-s4); }
.em-result-pauses { display: flex; flex-wrap: wrap; gap: var(--oui-s4) var(--oui-s8); }
</style>
