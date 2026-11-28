<script setup lang="ts">
import { computed } from 'vue';
import Message from 'primevue/message';
import { OuiIcon } from '@orca-plugins/ui-foundation/src/components';
import { info, layers, pause, target, warning } from '@orca-plugins/ui-foundation/src/icons';
import { s } from '../app/store';
import { locale, t, tMaybe, fmt, insertLabel } from '../core/i18n';

const mm = (v: number | null | undefined) => (v == null ? '—' : fmt.number(v, 2));
// Vents only widen a hexagon, square, rectangle or slot; a circle is its fit.
const outer = computed(() => (s.plan?.shape === 'circle' ? '' : (s.plan?.outer ?? []).map(v => fmt.number(v, 2)).join(' × ')));
/** The fit in the shape's own terms: a circle's diameter, a hexagon across its flats, a square's side, x × y. */
const fit = computed(() => {
  const [x, y, h] = (s.plan?.size ?? []).map(v => fmt.number(v, 2));
  if (h == null) return '';
  const shape = s.plan?.shape;
  const across = shape === 'circle' ? t('fit.circle', { d: x }) : shape === 'hexagon' ? t('fit.hexagon', { d: x })
    : shape === 'square' ? t('fit.square', { d: x }) : t('fit.rectangle', { x, y });
  return t('fit.deep', { fit: across, h });
});
const planned = computed(() => !!s.hit && !!s.plan && !s.plan.blocked);
/** "· top · embedded" after the insert: on which face, how. */
const how = computed(() => {
  const p = s.plan, lower = (text: string) => text.toLocaleLowerCase(locale.value);
  return !p ? '' : [p.face ? lower(tMaybe(`face.${p.face}`, p.face)) : '', lower(t(`mode.${p.mode}`))].filter(Boolean).map(v => ' · ' + v).join('');
});
/** Where the pocket is on the plate, as planned (the face's middle under Centre on the face), and how far it is
 *  turned. Said in a live region of its own, so a move with the arrow keys or a drop is announced; it is quiet during
 *  a drag, which would have it read out on every step of the pointer. */
const at = computed(() => {
  const [x, y, z] = (s.plan?.point ?? s.hit?.point ?? [0, 0, 0]).map(v => fmt.number(v, 1));
  return t(s.spin ? 'plan.atTurned' : 'plan.atValue', { x, y, z, spin: fmt.number(s.spin ?? 0, 0) });
});
</script>

<!-- The pocket the last click would make: a neutral block (raised, with a hairline) holding a prompt, then what
     matters at the printer (what goes in, where the print pauses, how much plastic covers it), and tinted as a warning
     when the pocket cannot be made. Its warnings come first, right under the heading. The geometry the plugin worked
     out for itself is behind Dimensions. Add pocket (under it) points here. -->
<template>
  <section class="em-plan" data-test="plan" aria-labelledby="plan-h">
    <div id="em-plan-state" class="oui-hero em-plan-block" :data-tone="s.hit && s.plan?.blocked ? 'warn' : undefined" :aria-live="s.dragging ? 'off' : 'polite'">
      <h3 id="plan-h" class="oui-label">{{ t('plan.title') }}</h3>
      <p v-if="!s.hit" class="em-note" data-test="plan-empty"><OuiIcon :icon="target" :size="16" />{{ t(s.webgl === false ? 'plan.emptyFallback' : 'plan.empty') }}</p>
      <p v-else-if="s.plan?.blocked" class="em-note" data-test="plan-blocked"><OuiIcon :icon="warning" tone="warn" :size="16" />
        {{ t('plan.blocked', { reason: tMaybe(`block.${s.plan.blocked.code}`, s.plan.blocked.detail || s.plan.blocked.code) }) }}</p>
      <template v-else-if="s.plan">
        <Message v-for="w in s.plan.warnings ?? []" :key="w" severity="warn" size="small" data-test="plan-warning">
          <template #icon><OuiIcon :icon="warning" :size="14" /></template>{{ tMaybe(`warn.${w}`, w) }}
        </Message>
        <dl class="em-facts oui-num">
          <dt>{{ t('plan.insert') }}</dt><dd><span data-test="plan-label">{{ insertLabel(s.plan.label) }}</span>{{ how }}</dd>
          <template v-if="s.plan.mode === 'embedded'">
            <dt><OuiIcon :icon="pause" :size="14" />{{ t('plan.pause') }}</dt><dd data-test="plan-pause">Z {{ mm(s.plan.pause_z) }} mm</dd>
            <dt><OuiIcon :icon="layers" :size="14" />{{ t('plan.cover') }}</dt><dd data-test="plan-cover">{{ mm(s.plan.cover) }} mm</dd>
          </template>
        </dl>
      </template>
      <p v-else class="em-note">{{ t('plan.working') }}</p>
      <!-- Said here, in the live region next to the plan, and not as a banner above the page: that would push the 3D
           view down under the pointer. -->
      <Message v-if="s.note" severity="info" size="small" data-test="plan-note">
        <template #icon><OuiIcon :icon="info" :size="14" /></template>{{ s.note }}
      </Message>
    </div>
    <p v-if="planned" class="oui-sr" data-test="plan-at-live" :aria-live="s.dragging ? 'off' : 'polite'">{{ t('plan.at') }}: {{ at }}</p>
    <details v-if="planned && s.plan" class="em-plan-more" data-test="plan-more">
      <summary>{{ t('plan.more') }}</summary>
      <dl class="em-facts oui-num">
        <dt>{{ t('plan.at') }}</dt><dd data-test="plan-at">{{ at }}</dd>
        <dt>{{ t('plan.size') }}</dt><dd data-test="plan-size">{{ fit }}</dd>
        <template v-if="s.plan.shape"><dt>{{ t('plan.shape') }}</dt><dd data-test="plan-shape">{{ tMaybe(`pocket.${s.plan.shape}`, s.plan.shape) }}</dd></template>
        <template v-if="outer"><dt>{{ t('plan.outer') }}</dt><dd data-test="plan-outer">{{ outer }} mm</dd></template>
        <template v-if="s.plan.mode === 'embedded'"><dt>{{ t('plan.cavity') }}</dt><dd>{{ t('plan.cavityRange', { floor: mm(s.plan.floor), top: mm(s.plan.top) }) }}</dd></template>
      </dl>
    </details>
  </section>
</template>

<style>
/* In the form's footer: as wide as the footer, and never taller than a share of the window (several warnings scroll
   inside it), so the button under it stays on screen. */
.em-plan { flex: 1 1 100%; display: grid; gap: var(--oui-s2); min-width: 0; max-height: 46vh; overflow-y: auto; }
.em-plan-block { gap: var(--oui-s2); padding: var(--oui-s3) var(--oui-s4); }
.em-plan-block:not([data-tone]) { box-shadow: inset 0 0 0 1px var(--oui-border); }
.em-plan-block > .em-note > .oui-icon { color: var(--oui-muted); }
.em-facts { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: 6px var(--oui-s4); }
.em-facts dt { display: inline-flex; align-items: center; gap: var(--oui-s1); color: var(--oui-muted); }
.em-facts dd { min-width: 0; font-weight: 700; overflow-wrap: anywhere; }
.em-plan-more > summary { width: fit-content; padding: 2px var(--oui-s1); border-radius: var(--oui-radius-sm); color: var(--oui-muted); font-size: var(--oui-text-sm); font-weight: 600; cursor: pointer; }
.em-plan-more > summary:hover { color: var(--oui-text); }
.em-plan-more > .em-facts { padding: var(--oui-s2) var(--oui-s4) var(--oui-s1); }
</style>
