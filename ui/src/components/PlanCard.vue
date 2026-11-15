<script setup lang="ts">
import { computed } from 'vue';
import Button from 'primevue/button';
import Message from 'primevue/message';
import Icon from './Icon.vue';
import { s } from '../app/store';
import { addStaged } from '../app/project';
import { t, tMaybe, fmt } from '../core/i18n';

const mm = (v: number | null | undefined) => (v == null ? '—' : fmt.number(v, 2));
const size = computed(() => (s.plan?.size ?? []).map(v => fmt.number(v, 2)).join(' × '));
</script>

<template>
  <section class="em-card em-plan" data-test="plan" aria-labelledby="plan-h" aria-live="polite">
    <h2 id="plan-h">{{ t('plan.title') }}</h2>
    <p v-if="!s.hit" class="oui-muted" data-test="plan-empty">{{ t(s.webgl === false ? 'plan.emptyFallback' : 'plan.empty') }}</p>
    <template v-else-if="s.plan?.blocked">
      <Message severity="warn" data-test="plan-blocked">
        {{ t('plan.blocked', { reason: tMaybe(`block.${s.plan.blocked.code}`, s.plan.blocked.detail || s.plan.blocked.code) }) }}
      </Message>
    </template>
    <template v-else-if="s.plan">
      <dl class="em-facts">
        <dt>{{ t('plan.insert') }}</dt><dd data-test="plan-label">{{ s.plan.label }}</dd>
        <dt>{{ t('plan.face') }}</dt><dd>{{ tMaybe(`face.${s.plan.face}`, s.plan.face ?? '') }} · {{ t(`mode.${s.plan.mode}`) }}</dd>
        <dt>{{ t('plan.size') }}</dt><dd>{{ size }} mm</dd>
        <template v-if="s.plan.mode === 'embedded'">
          <dt>{{ t('plan.cavity') }}</dt><dd>{{ t('plan.cavityRange', { floor: mm(s.plan.floor), top: mm(s.plan.top) }) }}</dd>
          <dt><Icon name="icon/pause" /> {{ t('plan.pause') }}</dt><dd data-test="plan-pause">Z {{ mm(s.plan.pause_z) }} mm</dd>
          <dt><Icon name="icon/layers" /> {{ t('plan.cover') }}</dt><dd>{{ mm(s.plan.cover) }} mm</dd>
        </template>
      </dl>
      <Message v-for="w in s.plan.warnings ?? []" :key="w" severity="warn" data-test="plan-warning">
        <Icon name="icon/warning" /> {{ tMaybe(`warn.${w}`, w) }}
      </Message>
      <Button data-test="add" @click="addStaged"><Icon name="icon/add" /><span>{{ t('plan.add') }}</span></Button>
    </template>
    <p v-else class="oui-muted">{{ t('plan.working') }}</p>
  </section>
</template>

<style scoped>
.em-plan { display: grid; gap: 12px; justify-items: start; }
.em-plan > h2 { margin: 0; }
.em-facts { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 12px; margin: 0; }
.em-facts dt { color: var(--oui-muted); display: inline-flex; align-items: center; gap: 4px; }
.em-facts dd { margin: 0; font-variant-numeric: tabular-nums; }
</style>
