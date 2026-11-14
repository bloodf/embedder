<script setup lang="ts">
import Button from 'primevue/button';
import Message from 'primevue/message';
import Icon from './Icon.vue';
import { s, tracker } from '../app/store';
import { openResult } from '../app/project';
import { t, tMaybe, fmt } from '../core/i18n';
</script>

<!-- After Apply the job is over: the new copy is the project now, so the page offers to open it and asks for
     Load project again before any more pockets (a second Apply on the old copy would drop the first one's). -->
<template>
  <section v-if="s.result" class="em-card em-result" data-test="result" aria-labelledby="result-h">
    <Icon name="spot/done" class="em-spot" />
    <h2 id="result-h">{{ t('result.title') }}</h2>
    <p>{{ t('result.body', { name: s.result.name, pockets: s.result.pockets, removed: s.result.removed }) }}</p>
    <p v-for="p in s.result.pauses" :key="p.top_z" class="oui-meta"><Icon name="icon/pause" /> Z {{ fmt.number(p.top_z, 2) }} mm · {{ p.extra }}</p>
    <Message v-for="w in s.result.warnings" :key="w" severity="warn"><Icon name="icon/warning" /> {{ tMaybe(`warn.${w}`, w) }}</Message>
    <p class="oui-meta">{{ t('result.copy') }}</p>
    <p class="oui-meta" data-test="result-next">{{ t('result.next') }}</p>
    <p class="oui-error-detail" data-test="result-path">{{ s.result.path }}</p>
    <Button :loading="tracker.isBusy('open')" data-test="open" @click="openResult"><Icon name="icon/folder" /><span>{{ t('result.open') }}</span></Button>
    <p v-if="s.opened" role="status" data-test="opened">{{ t(s.opened === 'asked' ? 'result.asked' : 'result.none') }}</p>
  </section>
</template>

<style scoped>
.em-result { display: grid; gap: 12px; justify-items: start; }
.em-result > h2 { margin: 0; }
</style>
