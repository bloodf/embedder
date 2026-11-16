<script setup lang="ts">
import { computed } from 'vue';
import Message from 'primevue/message';
import { OuiIcon } from '../../shared/src/components';
import { info, layers, pause, target, warning } from '../../shared/src/icons';
import { s } from '../app/store';
import { t, tMaybe, fmt, insertLabel } from '../core/i18n';

const mm = (v: number | null | undefined) => (v == null ? '—' : fmt.number(v, 2));
const size = computed(() => (s.plan?.size ?? []).map(v => fmt.number(v, 2)).join(' × '));
const outer = computed(() => (s.plan?.outer ?? []).map(v => fmt.number(v, 2)).join(' × '));
const planned = computed(() => !!s.hit && !!s.plan && !s.plan.blocked);
/** Where the pocket is on the plate, as planned (the face's middle under Centre on the face), and how far it is
 *  turned. This block is a live region, so a move with the arrow keys or a drop is announced through this line; it
 *  is quiet during a drag, which would have it read out on every step of the pointer. */
const at = computed(() => {
  const [x, y, z] = (s.plan?.point ?? s.hit?.point ?? [0, 0, 0]).map(v => fmt.number(v, 1));
  return t(s.spin ? 'plan.atTurned' : 'plan.atValue', { x, y, z, spin: fmt.number(s.spin ?? 0, 0) });
});
</script>

<!-- The pocket the last click would make: the page's one strongly coloured block once there is a plan, a quiet
     prompt before that, and a warning block when the pocket cannot be made. Add pocket (the panel footer) points here. -->
<template>
  <section class="em-plan" data-test="plan" aria-labelledby="plan-h" :aria-live="s.dragging ? 'off' : 'polite'">
    <div id="em-plan-state" class="oui-hero em-plan-block" :class="{ 'oui-on-band': planned }" :data-tone="planned ? undefined : s.hit && s.plan?.blocked ? 'warn' : 'accent'">
      <h3 id="plan-h" class="oui-label">{{ t('plan.title') }}</h3>
      <p v-if="!s.hit" class="em-note" data-test="plan-empty"><OuiIcon :icon="target" tone="accent" :size="16" />{{ t(s.webgl === false ? 'plan.emptyFallback' : 'plan.empty') }}</p>
      <p v-else-if="s.plan?.blocked" class="em-note" data-test="plan-blocked"><OuiIcon :icon="warning" tone="warn" :size="16" />
        {{ t('plan.blocked', { reason: tMaybe(`block.${s.plan.blocked.code}`, s.plan.blocked.detail || s.plan.blocked.code) }) }}</p>
      <dl v-else-if="s.plan" class="em-facts oui-num">
        <dt>{{ t('plan.insert') }}</dt><dd data-test="plan-label">{{ insertLabel(s.plan.label) }}</dd>
        <dt>{{ t('plan.face') }}</dt><dd>{{ tMaybe(`face.${s.plan.face}`, s.plan.face ?? '') }} · {{ t(`mode.${s.plan.mode}`) }}</dd>
        <dt>{{ t('plan.at') }}</dt><dd data-test="plan-at">{{ at }}</dd>
        <dt>{{ t('plan.size') }}</dt><dd>{{ size }} mm</dd>
        <template v-if="s.plan.shape"><dt>{{ t('plan.shape') }}</dt><dd data-test="plan-shape">{{ tMaybe(`pocket.${s.plan.shape}`, s.plan.shape) }}</dd></template>
        <template v-if="outer"><dt>{{ t('plan.outer') }}</dt><dd data-test="plan-outer">{{ outer }} mm</dd></template>
        <template v-if="s.plan.mode === 'embedded'">
          <dt>{{ t('plan.cavity') }}</dt><dd>{{ t('plan.cavityRange', { floor: mm(s.plan.floor), top: mm(s.plan.top) }) }}</dd>
          <dt><OuiIcon :icon="pause" :size="14" />{{ t('plan.pause') }}</dt><dd data-test="plan-pause">Z {{ mm(s.plan.pause_z) }} mm</dd>
          <dt><OuiIcon :icon="layers" :size="14" />{{ t('plan.cover') }}</dt><dd>{{ mm(s.plan.cover) }} mm</dd>
        </template>
      </dl>
      <p v-else class="em-note">{{ t('plan.working') }}</p>
    </div>
    <!-- Said here, in the live region next to the plan, and not as a banner above the page: that would push the 3D
         view down under the pointer. -->
    <Message v-if="s.note" severity="info" size="small" data-test="plan-note">
      <template #icon><OuiIcon :icon="info" :size="14" /></template>{{ s.note }}
    </Message>
    <template v-if="planned">
      <Message v-for="w in s.plan?.warnings ?? []" :key="w" severity="warn" size="small" data-test="plan-warning">
        <template #icon><OuiIcon :icon="warning" :size="14" /></template>{{ tMaybe(`warn.${w}`, w) }}
      </Message>
    </template>
  </section>
</template>

<style>
.em-plan { display: grid; gap: var(--oui-s2); margin-top: var(--oui-s4); }
.em-plan-block { gap: var(--oui-s2); padding: var(--oui-s3) var(--oui-s4); }
.em-facts { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 6px var(--oui-s4); }
.em-facts dt { display: inline-flex; align-items: center; gap: var(--oui-s1); color: var(--oui-muted); }
.em-facts dd { min-width: 0; font-weight: 700; overflow-wrap: anywhere; }
</style>
