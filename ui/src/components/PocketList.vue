<script setup lang="ts">
import { computed } from 'vue';
import Button from 'primevue/button';
import Checkbox from 'primevue/checkbox';
import { OuiEmpty, OuiHint, OuiIcon, OuiPanel } from '@orca-plugins/ui-foundation/src/components';
import { check, insert, layers, pause, rfid, trash, warning } from '@orca-plugins/ui-foundation/src/icons';
import { s, tracker } from '../app/store';
import { apply, markRemove, removeStaged, selectStaged } from '../app/project';
import { insertsNeeded, pauseSummary, splitLead } from '../app/logic';
import type { Staged } from '../app/types';
import { locale, t, tn, tMaybe, fmt, insertLabel } from '../core/i18n';

const pauses = computed(() => pauseSummary(s.staged).map(g => splitLead(t('pause.line', {
  z: fmt.number(g.z, 2), items: g.items.map(i => t('pause.item', { n: i.n, label: insertLabel(i.label) })).join(', ') }))));
const inserts = computed(() => insertsNeeded(s.staged));
const existing = computed(() => s.project?.existing ?? []);
const canApply = computed(() => !!(s.staged.length || s.remove.length) && !tracker.isBusy('apply'));
const empty = computed(() => splitLead(t('list.empty')));
const lower = (text: string) => text.toLocaleLowerCase(locale.value);
/** "Fridge tile · top · embedded · pause at Z 7.20 mm". The separator stays with the word before it, so a second line
 *  never starts with a dot. */
function where(p: Staged): string {
  return [s.project?.objects[p.args.object]?.name ?? '', p.plan.face ? lower(tMaybe(`face.${p.plan.face}`, p.plan.face)) : '', lower(t(`mode.${p.plan.mode}`)),
    p.plan.polarity ? t(`polarity.${p.plan.polarity}`) : '',
    p.plan.pause_z != null ? t('list.pauseAt', { z: fmt.number(p.plan.pause_z, 2) }) : ''].filter(Boolean).join(' · ');
}
</script>

<template>
  <OuiPanel :title="t('list.title')" :icon="layers" tone="lime" flush>
    <!-- How a staged pocket is changed and moved: behind the module's (i), once there is one to change. -->
    <template v-if="s.staged.length" #hint><span data-test="staged-help">{{ t(s.webgl === false ? 'list.helpFallback' : 'list.help') }}</span></template>
    <template #meta><span class="oui-chip oui-num" data-test="staged-count">{{ s.staged.length }}</span></template>

    <OuiEmpty v-if="!s.staged.length" compact :icon="layers" tone="lime" :title="empty[0]" :text="empty[1]" data-test="staged-empty" />
    <ul v-else class="em-rows" data-test="staged">
      <li v-for="p in s.staged" :key="p.key" :data-selected="s.selected === p.key || undefined">
        <!-- The row is a toggle: pressed, the pocket is in hand (the form changes it, the 3D view moves it). -->
        <button type="button" class="em-row-pick" :aria-pressed="s.selected === p.key" data-test="row-pick" @click="selectStaged(s.selected === p.key ? null : p.key)">
          <span class="em-kind em-kind-lg" :data-kind="p.plan.kind ?? 'magnet'"><OuiIcon :icon="p.plan.kind === 'nfc' ? rfid : insert" :size="16" /></span>
          <span class="em-row-id">
            <span class="oui-strong">{{ insertLabel(p.plan.label) }}</span>
            <span class="oui-meta">{{ where(p) }}</span>
            <span v-for="w in p.plan.warnings ?? []" :key="w" class="oui-meta em-warn em-note"><OuiIcon :icon="warning" :size="13" />{{ tMaybe(`warn.${w}`, w) }}</span>
          </span>
        </button>
        <Button text severity="danger" size="small" :aria-label="t('list.remove', { label: insertLabel(p.plan.label) })" @click="removeStaged(p.key)"><template #icon><OuiIcon :icon="trash" :size="14" /></template></Button>
      </li>
    </ul>

    <div v-if="inserts.length || pauses.length" class="em-ready">
      <template v-if="inserts.length">
        <p id="em-inserts-l" class="oui-label">{{ t('list.inserts') }}</p>
        <ul class="em-ready-list" aria-labelledby="em-inserts-l" data-test="inserts">
          <li v-for="i in inserts" :key="i.kind + i.label" class="em-ready-line"><span class="em-kind" :data-kind="i.kind" /><strong class="oui-num">{{ i.n }} ×</strong> {{ insertLabel(i.label) }}</li>
        </ul>
      </template>
      <template v-if="pauses.length">
        <p id="em-pauses-l" class="oui-label">{{ t('list.pauses') }}</p>
        <ul class="em-ready-list" aria-labelledby="em-pauses-l" data-test="pauses">
          <li v-for="line in pauses" :key="line[0] + line[1]" class="em-ready-line oui-num"><OuiIcon :icon="pause" :size="14" /><span><strong>{{ line[0] }}</strong> {{ line[1] }}</span></li>
        </ul>
      </template>
    </div>

    <div v-if="existing.length" class="em-ready em-existing">
      <div class="em-labelled"><p id="em-existing-l" class="oui-label">{{ t('list.existing') }}</p><OuiHint :label="t('list.existing')">{{ t('list.existingHelp') }}</OuiHint></div>
      <ul class="em-ready-list" aria-labelledby="em-existing-l" data-test="existing">
        <li v-for="x in existing" :key="x.id">
          <label class="em-check" :for="'rm-' + x.id"><Checkbox :model-value="s.remove.includes(x.id)" binary :input-id="'rm-' + x.id" @update:model-value="markRemove(x.id, $event)" />
            {{ t('list.removeExisting', { label: insertLabel(x.label), mode: t(`mode.${x.mode}`) }) }}</label>
        </li>
      </ul>
    </div>

    <template #footer>
      <span class="oui-meta em-summary" data-test="summary">{{ tn('list.summary', s.staged.length, { removed: s.remove.length }) }}</span>
      <Button :label="t('list.apply')" class="em-apply" :disabled="!canApply" :loading="tracker.isBusy('apply')" data-test="apply" @click="apply">
        <template #icon><OuiIcon :icon="check" :size="14" /></template></Button>
    </template>
  </OuiPanel>
</template>

<style>
/* foundation-gap: the foundation has no selectable list row (a row that is a toggle and shows which one is chosen), nor
   a focus ring drawn inside an element that fills its container.
   A staged pocket's row is a toggle button over the whole row but the trash button. The pocket in hand is marked by a
   bar and a tint as well as by aria-pressed. */
.em-row-pick { flex: 1 1 0; align-self: stretch; display: flex; align-items: center; gap: var(--oui-s3); min-width: 0;
  margin: calc(-1 * var(--oui-s2)) 0 calc(-1 * var(--oui-s2)) calc(-1 * var(--oui-s4)); padding: var(--oui-s2) 0 var(--oui-s2) var(--oui-s4);
  appearance: none; border: 0; background: none; font: inherit; color: inherit; text-align: start; cursor: pointer; }
.orca-ui .em-row-pick:focus-visible { outline-offset: -2px; }
.em-rows > li:has(> .em-row-pick:hover) { background: var(--oui-raised); }
.em-rows > li[data-selected] { background: var(--oui-primary-soft); box-shadow: inset 3px 0 0 var(--oui-primary-mark); }
.em-ready { display: grid; gap: var(--oui-s1); padding: var(--oui-s4); }
.em-ready > .oui-label:not(:first-child) { margin-top: var(--oui-s3); }
.em-ready + .em-ready { border-top: 1px solid var(--oui-border); }
.em-ready-list { display: grid; gap: var(--oui-s1); list-style: none; padding: 0; }
.em-ready-line { display: flex; align-items: baseline; gap: var(--oui-s2); }
.em-ready-line > .em-kind { align-self: center; }
.em-ready-line > .oui-icon { align-self: flex-start; margin-top: 2px; color: var(--oui-muted); }
.em-existing .em-check { width: auto; }
.em-list .oui-panel-foot { margin-top: auto; }
.em-summary { flex: 1 1 100%; }
.em-apply { margin-inline-start: auto; }
</style>
