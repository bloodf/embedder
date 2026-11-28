<script setup lang="ts">
import { computed, ref } from 'vue';
import Button from 'primevue/button';
import Checkbox from 'primevue/checkbox';
import Message from 'primevue/message';
import { OuiEmpty, OuiHint, OuiIcon, OuiListRow, OuiPanel } from '@orca-plugins/ui-foundation/src/components';
import { check, layers, pause, trash, warning } from '@orca-plugins/ui-foundation/src/icons';
import ExistingPockets from './ExistingPockets.vue';
import { s, tracker } from '../app/store';
import { apply, autoFridge, removeStaged, selectStaged } from '../app/project';
import { HOLD_WARNINGS, insertsNeeded, ownWarnings, pauseSummary, sharedWarnings, splitLead } from '../app/logic';
import type { Staged } from '../app/types';
import { locale, t, tn, tMaybe, fmt, insertLabel, listOf } from '../core/i18n';

const pauses = computed(() => pauseSummary(s.staged).map(g => splitLead(t('pause.line', {
  z: fmt.number(g.z, 2), items: g.items.map(i => tn('pause.item', i.n, { label: insertLabel(i.label) })).join(', ') }))));
const inserts = computed(() => insertsNeeded(s.staged));
const existing = computed(() => s.project?.existing ?? []);
const several = computed(() => (s.project?.objects.length ?? 0) > 1);
const canApply = computed(() => !!(s.staged.length || s.remove.length) && !tracker.isBusy('apply'));
const empty = computed(() => splitLead(t('list.empty')));
const lower = (text: string) => text.toLocaleLowerCase(locale.value);
const objectName = (k: number) => {
  const o = s.project?.objects[k];
  return !o ? '' : o.instance ? t('obj.instance', { name: o.name, n: o.instance + 1 }) : o.name;
};
/** "Fridge tile · top · embedded · pause at Z 7.20 mm". The separator stays with the word before it, so a second line
 *  never starts with a dot. */
function where(p: Staged): string {
  return [s.project?.objects[p.args.object]?.name ?? '', p.plan.face ? lower(tMaybe(`face.${p.plan.face}`, p.plan.face)) : '', lower(t(`mode.${p.plan.mode}`)),
    p.plan.polarity ? t(`polarity.${p.plan.polarity}`) : '',
    p.plan.pause_z != null ? t('list.pauseAt', { z: fmt.number(p.plan.pause_z, 2) }) : ''].filter(Boolean).join(' · ');
}
// The hold advisories of auto fridge are about all the magnets of an object together: each is said once above the
// rows (naming the objects when the plate has several), and the rows it covers only carry a mark.
const holds = computed(() => sharedWarnings(s.staged).map(w => {
  const text = tMaybe(`warn.${w.code}`, w.code);
  return { code: w.code, text: several.value ? t('list.forObjects', { names: listOf(w.objects.map(objectName)), text }) : text };
}));
const held = (p: Staged) => (p.plan.warnings ?? []).filter(w => HOLD_WARNINGS.includes(w));
const heldTitle = (p: Staged) => held(p).map(w => tMaybe(`warn.${w}`, w)).join(' ');
/** "2 pockets to add and 1 pocket to remove. Apply writes a new copy."; nothing while there is nothing to apply. */
const summary = computed(() => {
  const parts = [s.staged.length ? tn('list.toAdd', s.staged.length) : '', s.remove.length ? tn('list.toRemove', s.remove.length) : ''].filter(Boolean);
  return parts.length ? t('list.summary', { what: listOf(parts) }) : '';
});
const fridgeAll = ref(false);
const fridge = (count: 'auto' | number) => autoFridge(count, several.value && fridgeAll.value);
const FRIDGE_COUNTS = [1, 2, 4];
</script>

<template>
  <OuiPanel :title="t('list.title')" :icon="layers" tone="lime" flush>
    <!-- How a staged pocket is changed and moved: behind the module's (i), once there is one to change. -->
    <template v-if="s.staged.length" #hint><span data-test="staged-help">{{ t(s.webgl === false ? 'list.helpFallback' : 'list.help') }}</span></template>
    <template #meta><span class="oui-chip oui-num" data-test="staged-count">{{ s.staged.length }}</span></template>

    <!-- With nothing staged yet, what the project already holds is the panel's content: it comes first. -->
    <ExistingPockets v-if="existing.length && !s.staged.length" />
    <OuiEmpty v-if="!s.staged.length" compact :icon="layers" tone="lime" :title="empty[0]" :text="empty[1]" data-test="staged-empty" />
    <template v-else>
      <div v-if="holds.length" class="em-holds" data-test="hold-warnings">
        <Message v-for="w in holds" :key="w.code" severity="warn" size="small" data-test="hold-warning">
          <template #icon><OuiIcon :icon="warning" :size="14" /></template>{{ w.text }}
        </Message>
      </div>
      <ul class="oui-list em-staged" data-test="staged">
        <!-- The row is a toggle: pressed, the pocket is in hand (the form changes it, the 3D view moves it). -->
        <OuiListRow v-for="(p, i) in s.staged" :key="p.key" selectable :selected="s.selected === p.key" @update:selected="selectStaged($event ? p.key : null)">
          <!-- Its number, in the colour of its kind: the pocket in the 3D view carries the same one. -->
          <span class="em-kind em-kind-lg oui-num" :data-kind="p.plan.kind ?? 'magnet'" data-test="row-n">{{ i + 1 }}</span>
          <span class="em-row-id">
            <span class="oui-strong">{{ insertLabel(p.plan.label) }}</span>
            <span class="oui-meta">{{ where(p) }}</span>
            <span v-for="w in ownWarnings(p.plan)" :key="w" class="oui-meta em-warn em-note" data-test="row-warning"><OuiIcon :icon="warning" :size="13" />{{ tMaybe(`warn.${w}`, w) }}</span>
          </span>
          <!-- The hold advice said once above the rows covers this pocket: a mark to see, the sentence to hear. -->
          <span v-if="held(p).length" class="em-row-flag em-warn" :title="heldTitle(p)" data-test="row-hold"><OuiIcon :icon="warning" :size="13" /><span class="oui-sr">{{ heldTitle(p) }}</span></span>
          <template #actions>
            <Button text severity="danger" size="small" :aria-label="t('list.remove', { label: (i + 1) + ' · ' + insertLabel(p.plan.label) })" @click="removeStaged(p.key)"><template #icon><OuiIcon :icon="trash" :size="14" /></template></Button>
          </template>
        </OuiListRow>
      </ul>
    </template>

    <!-- Fridge magnets are placed for you, with the insert and the pocket type chosen in the form: an action, so it
         sits with the list it fills and not among the form's settings. -->
    <div class="em-ready">
      <div class="em-labelled">
        <p id="fridge-l" class="oui-label">{{ t('form.autoFridge') }}</p>
        <OuiHint :label="t('form.autoFridge')"><span id="fridge-help">{{ t('form.autoFridgeHelp') }}</span></OuiHint>
      </div>
      <div class="em-fridge" role="group" aria-labelledby="fridge-l" aria-describedby="fridge-help" data-test="auto-fridge">
        <Button :label="t('form.autoFridgeAuto')" severity="secondary" size="small" fluid :loading="tracker.isBusy('auto-fridge')" data-test="auto-fridge-auto" @click="fridge('auto')" />
        <Button v-for="n in FRIDGE_COUNTS" :key="n" :label="String(n)" :aria-label="tn('form.autoFridgeN', n)" severity="secondary" size="small" fluid
                :disabled="tracker.isBusy('auto-fridge')" :data-test="`auto-fridge-${n}`" @click="fridge(n)" />
      </div>
      <label v-if="several" class="em-check" for="f-fridge-all"><Checkbox v-model="fridgeAll" binary input-id="f-fridge-all" data-test="auto-fridge-all" />{{ t('form.autoFridgeAll') }}</label>
    </div>

    <div v-if="inserts.length || pauses.length" class="em-ready">
      <template v-if="inserts.length">
        <p id="em-inserts-l" class="oui-label">{{ t('list.inserts') }}</p>
        <ul class="em-ready-list" aria-labelledby="em-inserts-l" data-test="inserts">
          <li v-for="i in inserts" :key="i.kind + i.label" class="em-ready-line"><span class="em-kind" :data-kind="i.kind" /><span class="oui-chip oui-num">{{ i.n }}</span> {{ insertLabel(i.label) }}</li>
        </ul>
      </template>
      <template v-if="pauses.length">
        <p id="em-pauses-l" class="oui-label">{{ t('list.pauses') }}</p>
        <ul class="em-ready-list" aria-labelledby="em-pauses-l" data-test="pauses">
          <li v-for="line in pauses" :key="line[0] + line[1]" class="em-ready-line oui-num"><OuiIcon :icon="pause" :size="14" /><span><strong>{{ line[0] }}</strong> {{ line[1] }}</span></li>
        </ul>
      </template>
    </div>

    <ExistingPockets v-if="existing.length && s.staged.length" />

    <template #footer>
      <span v-if="summary" class="oui-meta em-summary" data-test="summary">{{ summary }}</span>
      <Button :label="t('list.apply')" class="em-apply" :disabled="!canApply" :loading="tracker.isBusy('apply')" data-test="apply" @click="apply">
        <template #icon><OuiIcon :icon="check" :size="14" /></template></Button>
    </template>
  </OuiPanel>
</template>

<style>
/* The staged list is one block among several in the panel: its last row keeps the hairline that parts it from the next. */
.em-staged.oui-list > .oui-listrow:last-child { border-bottom: 1px solid var(--oui-border); }
.em-row-flag { flex: none; display: inline-grid; }
.em-holds { display: grid; gap: var(--oui-s2); padding: var(--oui-s3) var(--oui-s4); border-bottom: 1px solid var(--oui-border); }
/* The panel's blocks keep their height and the body scrolls (in the layouts where the panel has a height of its own):
   nothing is squeezed under the footer. The empty state takes the room that is left. */
.em-list > .oui-panel-body { display: flex; flex-direction: column; }
.em-list > .oui-panel-body > * { flex: none; }
.em-list > .oui-panel-body > .oui-empty { flex: 1 0 auto; min-height: 96px; }   /* not the foundation's 100%: the blocks under it stay in sight */
.em-ready { display: grid; gap: var(--oui-s1); padding: var(--oui-s4); }
.em-ready > .oui-label:not(:first-child) { margin-top: var(--oui-s3); }
.em-list .oui-panel-body > :not(.em-staged) + .em-ready { border-top: 1px solid var(--oui-border); }
.em-ready-list { display: grid; gap: var(--oui-s1); list-style: none; padding: 0; }
.em-ready-line { display: flex; align-items: baseline; gap: var(--oui-s2); }
.em-ready-line > .em-kind { align-self: center; }
.em-ready-line > .oui-icon { align-self: flex-start; margin-top: 2px; color: var(--oui-muted); }
.em-fridge { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--oui-s2); }
.em-ready > .em-check { margin-top: var(--oui-s1); }
.em-summary { flex: 1 1 100%; }
.em-apply { margin-inline-start: auto; }
</style>
