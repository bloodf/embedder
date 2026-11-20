<script setup lang="ts">
import Button from 'primevue/button';
import Message from 'primevue/message';
import { OuiBanner, OuiIcon, OuiPanel, OuiReadout, OuiStatus } from '@orca-plugins/ui-foundation/src/components';
import { external, file, pause, warning } from '@orca-plugins/ui-foundation/src/icons';
import { s, tracker } from '../app/store';
import { openResult } from '../app/project';
import { t, tn, tMaybe, fmt } from '../core/i18n';
</script>

<!-- After Apply the job is over: the new copy is the project now, so the page offers to open it and asks for
     Load project again before any more pockets (a second Apply on the old copy would drop the first one's). -->
<template>
  <section v-if="s.result" class="em-result" data-test="result" :aria-label="t('result.title')">
    <OuiBanner tone="success" :title="t('result.title')" data-test="result-banner" dismissible :dismiss-key="'result:' + s.applies + ':' + s.result.path" :close-label="t('common.close')"><span>{{ t('result.body', { name: s.result.name, pockets: s.result.pockets, removed: s.result.removed }) }}</span></OuiBanner>

    <OuiPanel :title="s.result.name" :icon="file" flush>
      <!-- What to do at the printer is the main line: where the print stops and what goes in. -->
      <div v-if="s.result.pauses.length" class="oui-hero em-result-pauses">
        <OuiReadout v-for="p in s.result.pauses" :key="p.top_z" :icon="pause" :label="t('plan.pause')" :value="'Z ' + fmt.number(p.top_z, 2)" unit="mm" size="lg" :sub="p.extra" />
      </div>
      <div class="em-result-body">
        <Message v-for="w in s.result.warnings" :key="w" severity="warn" size="small">
          <template #icon><OuiIcon :icon="warning" :size="14" /></template>{{ tMaybe(`warn.${w}`, w) }}
        </Message>
        <p class="oui-error-detail oui-well em-result-path" data-test="result-path">{{ s.result.path }}</p>
        <p class="oui-meta">{{ t('result.copy') }}</p>
        <p v-if="s.result.pruned" class="oui-meta" data-test="result-pruned">{{ tn('result.pruned', s.result.pruned) }}</p>
        <p class="oui-meta" data-test="result-next">{{ t('result.next') }}</p>
      </div>
      <template #footer>
        <Button :label="t('result.open')" :loading="tracker.isBusy('open')" data-test="open" @click="openResult"><template #icon><OuiIcon :icon="external" :size="14" /></template></Button>
        <span role="status" class="em-result-opened">
          <OuiStatus v-if="s.opened" :state="s.opened === 'asked' ? 'pending' : 'warn'" variant="plain" data-test="opened">{{ t(s.opened === 'asked' ? 'result.asked' : 'result.none') }}</OuiStatus>
        </span>
      </template>
    </OuiPanel>
  </section>
</template>

<style>
.em-result { display: grid; gap: var(--oui-s3); justify-self: center; width: min(100%, 880px); margin-top: var(--oui-s4); }
.em-result-pauses { display: flex; flex-wrap: wrap; gap: var(--oui-s4) var(--oui-s8); margin: var(--oui-s4) var(--oui-s4) 0; }
.em-result-body { display: grid; gap: var(--oui-s2); padding: var(--oui-s4); }
.em-result-path { padding: var(--oui-s2) var(--oui-s3); user-select: all; }
.em-result-opened { flex: 1 1 200px; min-width: 0; }
.em-result-opened .oui-status { white-space: normal; }
</style>
