<script setup lang="ts">
import { computed } from 'vue';
import Button from 'primevue/button';
import Checkbox from 'primevue/checkbox';
import Message from 'primevue/message';
import Icon from './Icon.vue';
import { s, tracker } from '../app/store';
import { apply, markRemove, openResult, removeStaged } from '../app/project';
import { pauseSummary } from '../app/logic';
import { t, tn, tMaybe, fmt } from '../core/i18n';

const pauses = computed(() => pauseSummary(s.staged).map(g => t('pause.line', {
  z: fmt.number(g.z, 2), items: g.items.map(i => t('pause.item', { n: i.n, label: i.label })).join(', ') })));
const existing = computed(() => s.project?.existing ?? []);
const canApply = computed(() => !!(s.staged.length || s.remove.length) && !tracker.isBusy('apply'));
const objectName = (k: number) => s.project?.objects[k]?.name ?? '';
</script>

<template>
  <section class="em-card em-list" aria-labelledby="list-h">
    <h2 id="list-h">{{ t('list.title') }}</h2>
    <p v-if="!s.staged.length" class="oui-muted" data-test="staged-empty">{{ t('list.empty') }}</p>
    <ul v-else class="em-rows" data-test="staged">
      <li v-for="p in s.staged" :key="p.key" class="em-item">
        <Icon :name="p.plan.kind === 'nfc' ? 'icon/nfc' : 'icon/magnet'" />
        <span class="em-item-main">
          <strong>{{ p.plan.label }}</strong> · {{ t(`mode.${p.plan.mode}`) }}
          <span class="oui-meta">{{ objectName(p.args.object) }}<template v-if="p.plan.pause_z != null"> · {{ t('list.pauseAt', { z: fmt.number(p.plan.pause_z, 2) }) }}</template></span>
          <span v-for="w in p.plan.warnings ?? []" :key="w" class="oui-meta em-warn"><Icon name="icon/warning" /> {{ tMaybe(`warn.${w}`, w) }}</span>
        </span>
        <Button text severity="danger" size="small" :aria-label="t('list.remove', { label: p.plan.label })" @click="removeStaged(p.key)"><Icon name="icon/delete" /></Button>
      </li>
    </ul>

    <div v-if="pauses.length" class="em-pauses" data-test="pauses">
      <p v-for="line in pauses" :key="line"><Icon name="icon/pause" /> {{ line }}</p>
    </div>

    <template v-if="existing.length">
      <h3>{{ t('list.existing') }}</h3>
      <p class="oui-meta">{{ t('list.existingHelp') }}</p>
      <ul class="em-rows" data-test="existing">
        <li v-for="x in existing" :key="x.id" class="em-item">
          <Checkbox :model-value="s.remove.includes(x.id)" binary :input-id="'rm-' + x.id" @update:model-value="markRemove(x.id, $event)" />
          <label :for="'rm-' + x.id">{{ t('list.removeExisting', { label: x.label, mode: t(`mode.${x.mode}`) }) }}</label>
        </li>
      </ul>
    </template>

    <div class="em-row">
      <Button :disabled="!canApply" :loading="tracker.isBusy('apply')" data-test="apply" @click="apply">
        <Icon name="icon/check" /><span>{{ t('list.apply') }}</span></Button>
      <span class="oui-meta">{{ tn('list.summary', s.staged.length, { removed: s.remove.length }) }}</span>
    </div>
  </section>

  <section v-if="s.result" class="em-card em-result" data-test="result" aria-labelledby="result-h">
    <Icon name="spot/done" class="em-spot" />
    <h2 id="result-h">{{ t('result.title') }}</h2>
    <p>{{ t('result.body', { name: s.result.name, pockets: s.result.pockets, removed: s.result.removed }) }}</p>
    <p v-for="p in s.result.pauses" :key="p.top_z" class="oui-meta"><Icon name="icon/pause" /> Z {{ fmt.number(p.top_z, 2) }} mm · {{ p.extra }}</p>
    <Message v-for="w in s.result.warnings" :key="w" severity="warn"><Icon name="icon/warning" /> {{ tMaybe(`warn.${w}`, w) }}</Message>
    <p class="oui-meta">{{ t('result.copy') }}</p>
    <p class="oui-error-detail" data-test="result-path">{{ s.result.path }}</p>
    <Button :loading="tracker.isBusy('open')" data-test="open" @click="openResult"><Icon name="icon/folder" /><span>{{ t('result.open') }}</span></Button>
    <p v-if="s.opened" role="status" data-test="opened">{{ t(s.opened === 'asked' ? 'result.asked' : 'result.none') }}</p>
  </section>
</template>

<style scoped>
.em-list, .em-result { display: grid; gap: 12px; }
.em-list > h2, .em-result > h2, .em-list h3 { margin: 0; }
.em-result { justify-items: start; }
.em-rows { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.em-item { display: flex; align-items: center; gap: 8px; }
.em-item-main { flex: 1; display: grid; gap: 2px; min-width: 0; }
.em-pauses p { display: flex; align-items: center; gap: 6px; margin: 0; }
</style>
