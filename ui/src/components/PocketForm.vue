<script setup lang="ts">
import { computed, watch } from 'vue';
import Button from 'primevue/button';
import Select from 'primevue/select';
import SelectButton from 'primevue/selectbutton';
import InputNumber from 'primevue/inputnumber';
import Checkbox from 'primevue/checkbox';
import { OuiHint, OuiIcon, OuiPanel } from '@orca-plugins/ui-foundation/src/components';
import { check, insert, magnet, plus, rfid, save, user, type OuiIconData } from '@orca-plugins/ui-foundation/src/icons';
import PlanCard from './PlanCard.vue';
import { choosePocketShape, choosePreset, s, savePreset, tracker } from '../app/store';
import { addStaged, autoFridge, canAdd as addable, currentObject, replan, selectObject, selectStaged } from '../app/project';
import { customDims, defaultPocketShape, embeddedBlock, groupPresets, POCKET_SHAPES } from '../app/logic';
import type { Custom, PocketShape, Preset } from '../app/types';
import { prompt } from '../core/dialog';
import { locale, t, tMaybe, fmt } from '../core/i18n';
import { vDecimal } from '../core/decimal';

const n = (v: number | undefined) => fmt.number(v ?? 0, 1).replace(/[.,]0$/, '');
function presetLabel(p: Preset): string {
  if (!p.builtin) return p.name;
  if (p.id.startsWith('nfc-sticker')) return t('preset.sticker', { d: n(p.d) });
  if (p.id.startsWith('nfc-coin')) return t('preset.coin', { d: n(p.d), t: n(p.t) });
  if (p.id === 'nfc-card') return t('preset.card', { l: n(p.l), w: n(p.w), t: n(p.t) });
  if (p.id.startsWith('nut-hex-m')) return t('preset.hexNut', { size: p.id.slice('nut-hex-m'.length).toUpperCase() });
  if (p.id.startsWith('nut-square-m')) return t('preset.squareNut', { size: p.id.slice('nut-square-m'.length).toUpperCase() });
  return p.shape === 'disc' ? t('preset.disc', { d: n(p.d), t: n(p.t) }) : t('preset.block', { l: n(p.l), w: n(p.w), t: n(p.t) });
}

const GROUP_ICON = { magnet, nfc: rfid, nut: insert, mine: user };
const groups = computed(() => groupPresets(s.builtin, s.user).map(g => ({
  label: t(`group.${g.key}`), icon: GROUP_ICON[g.key], items: g.items.map(p => ({ id: p.id, label: presetLabel(p), kind: p.kind })) })));
const chosen = computed(() => groups.value.flatMap(g => g.items).find(p => p.id === s.insert.preset));
const objects = computed(() => (s.project?.objects ?? []).map(o => ({
  value: o.object, label: o.instance ? t('obj.instance', { name: o.name, n: o.instance + 1 }) : o.name })));
const block = computed(() => embeddedBlock(currentObject(), s.plan));
// A reason the banner above the panels already gives for the whole plate is not said again under the control.
const blockSaidAbove = computed(() => !!block.value && (s.project?.blocks ?? []).includes(block.value));
const modes = computed(() => [
  { value: 'embedded', label: t('mode.embedded'), disabled: !!block.value },
  { value: 'open', label: t('mode.open'), disabled: false }]);
const coverDefault = computed(() => {
  const kind = s.insert.custom?.kind ?? [...s.builtin, ...s.user].find(p => p.id === s.insert.preset)?.kind ?? 'magnet';
  return (kind === 'nfc' ? s.settings?.cover_nfc : s.settings?.cover_magnet) ?? 1;
});
const kinds = computed(() => [
  { value: 'magnet', label: t('kind.magnet') },
  { value: 'nfc', label: t('kind.nfc') },
  { value: 'nut', label: t('kind.nut') },
]);
const insertKind = computed(() => s.insert.custom?.kind ?? [...s.builtin, ...s.user].find(p => p.id === s.insert.preset)?.kind ?? 'magnet');
const coverDefault = computed(() => (insertKind.value === 'nfc' ? s.settings?.cover_nfc : s.settings?.cover_magnet) ?? 1);
const polarities = computed(() => [
  { value: null, label: t('polarity.none') },
  { value: 'N', label: t('polarity.N') },
  { value: 'S', label: t('polarity.S') },
]);
const kinds = computed(() => [{ value: 'magnet', label: t('kind.magnet') }, { value: 'nfc', label: t('kind.nfc') }]);
const shapes = computed(() => [{ value: 'disc', label: t('shape.disc') }, { value: 'block', label: t('shape.block') }]);
const canAdd = computed(addable);

// The pocket's outline, drawn on the icon grid as the pocket lies with no rotation: the hexagon's corners on X.
const SHAPE_ICON: Record<PocketShape, OuiIconData> = {
  circle: [['circle', { cx: 12, cy: 12, r: 9 }]],
  hexagon: [['path', { d: 'M2.5 12 7.25 3.8h9.5L21.5 12l-4.75 8.2h-9.5Z' }]],
  square: [['rect', { x: 4, y: 4, width: 16, height: 16, rx: 1.5 }]],
  rectangle: [['rect', { x: 2, y: 6.5, width: 20, height: 11, rx: 1.5 }]],
};
const insertShape = computed(() => s.insert.custom?.shape ?? [...s.builtin, ...s.user].find(p => p.id === s.insert.preset)?.shape ?? 'disc');
const pocketShape = computed(() => s.pocketShape ?? defaultPocketShape(insertShape.value));
// Embedded on an upright side face the insert stands on edge in its slot, whatever shape is picked.
const inSlot = computed(() => s.mode === 'embedded' && !!s.hit && s.plan?.face === 'side');
const pocketShapes = computed(() => POCKET_SHAPES.map(v => ({ value: v, label: t(`cut.${v}`), icon: SHAPE_ICON[v] })));

function setCustom(on: boolean) {
  const fresh: Custom = { kind: 'magnet', shape: 'disc', d: 6, l: 10, w: 5, t: 3 };
  if (on) s.insert = { preset: s.insert.preset, custom: fresh }; else choosePreset(s.insert.preset);
}
function setDim(key: keyof Custom, value: unknown) {
  if (s.insert.custom) s.insert = { ...s.insert, custom: { ...s.insert.custom, [key]: value } as Custom };
}
async function saveAsPreset() {
  const custom = s.insert.custom;
  if (!custom) return;
  const name = await prompt({ title: t('preset.saveTitle'), text: t('preset.saveText'), yes: t('common.save'), input: { label: t('preset.name'), value: '' } });
  if (!name?.trim()) return;
  const id = await savePreset({ name: name.trim(), ...customDims(custom) });
  if (!id) return;
  const picked = s.pocketShape;
  choosePreset(id);
  if (picked) void choosePocketShape(picked);   // the new preset keeps the shape it was made with
}

watch(insertKind, k => { if (k !== 'magnet' && s.polarity != null) s.polarity = null; });
watch(() => [s.insert, s.mode, s.spin, s.cover, s.center, s.pocketShape, s.polarity], () => { void replan(); });
</script>

<template>
  <!-- The same form places a new pocket and changes the pocket of the list that is in hand. -->
  <OuiPanel :title="t(s.selected == null ? 'form.title' : 'form.titleSelected')" :icon="insert">
    <div class="oui-stack">
      <div class="oui-field">
        <label id="obj-l">{{ t('form.object') }}</label>
        <Select :model-value="s.object" :options="objects" option-label="label" option-value="value" aria-labelledby="obj-l" data-test="object" fluid
                @update:model-value="selectObject($event)" />
      </div>

      <div class="oui-field">
        <label id="ins-l">{{ t('form.insert') }}</label>
        <Select v-if="!s.insert.custom" :model-value="s.insert.preset" :options="groups" option-group-label="label" option-group-children="items"
                option-label="label" option-value="id" aria-labelledby="ins-l" data-test="preset" fluid scroll-height="min(320px, 50vh)"
                @update:model-value="choosePreset($event)">
          <template #value="{ value, placeholder }">
            <span v-if="chosen && value" class="em-opt"><span class="em-kind" :data-kind="chosen.kind" />{{ chosen.label }}</span>
            <template v-else>{{ placeholder }}&nbsp;</template>
          </template>
          <template #optiongroup="{ option }"><span class="em-opt em-group"><OuiIcon :icon="option.icon" :size="14" />{{ option.label }}</span></template>
          <template #option="{ option }"><span class="em-opt"><span class="em-kind" :data-kind="option.kind" />{{ option.label }}</span></template>
        </Select>
        <label class="em-check" for="f-custom"><Checkbox :model-value="!!s.insert.custom" binary input-id="f-custom" data-test="custom" @update:model-value="setCustom($event)" />{{ t('form.custom') }}</label>
      </div>

      <div v-if="s.insert.custom" class="em-custom oui-well" data-test="custom-dims">
        <div class="em-two">
          <div class="oui-field"><label id="k-l">{{ t('form.kind') }}</label>
            <Select :model-value="s.insert.custom.kind" :options="kinds" option-label="label" option-value="value" aria-labelledby="k-l" fluid @update:model-value="setDim('kind', $event)">
              <template #value="{ value }"><span class="em-opt"><span class="em-kind" :data-kind="value" />{{ t(`kind.${s.insert.custom.kind}`) }}</span></template>
            </Select></div>
          <div class="oui-field"><label id="sh-l">{{ t('form.shape') }}</label>
            <Select :model-value="s.insert.custom.shape" :options="shapes" option-label="label" option-value="value" aria-labelledby="sh-l" fluid @update:model-value="setDim('shape', $event)" /></div>
        </div>
        <div class="em-two" :data-three="s.insert.custom.shape === 'block' || undefined">
          <div v-if="s.insert.custom.shape === 'disc'" class="oui-field"><label for="f-d">{{ t('form.d') }}</label>
            <InputNumber v-decimal :locale="locale" input-id="f-d" :model-value="s.insert.custom.d" :min="0.1" :max="300" :max-fraction-digits="2" suffix=" mm" fluid @update:model-value="setDim('d', $event)" /></div>
          <template v-else>
            <div class="oui-field"><label for="f-l">{{ t('form.l') }}</label>
              <InputNumber v-decimal :locale="locale" input-id="f-l" :model-value="s.insert.custom.l" :min="0.1" :max="300" :max-fraction-digits="2" suffix=" mm" fluid @update:model-value="setDim('l', $event)" /></div>
            <div class="oui-field"><label for="f-w">{{ t('form.w') }}</label>
              <InputNumber v-decimal :locale="locale" input-id="f-w" :model-value="s.insert.custom.w" :min="0.1" :max="300" :max-fraction-digits="2" suffix=" mm" fluid @update:model-value="setDim('w', $event)" /></div>
          </template>
          <div class="oui-field"><label for="f-t">{{ t('form.t') }}</label>
            <InputNumber v-decimal :locale="locale" input-id="f-t" :model-value="s.insert.custom.t" :min="0.1" :max="300" :max-fraction-digits="2" suffix=" mm" fluid @update:model-value="setDim('t', $event)" /></div>
        </div>
        <Button :label="t('preset.saveAs')" severity="secondary" size="small" data-test="save-preset" @click="saveAsPreset"><template #icon><OuiIcon :icon="save" :size="14" /></template></Button>
      </div>

      <div class="oui-field">
        <div class="em-labelled"><label id="cut-l">{{ t('form.pocketShape') }}</label>
          <OuiHint v-if="!inSlot" :label="t('form.pocketShape')"><span id="cut-help">{{ t('form.pocketShapeHelp', { shape: t(`cut.${defaultPocketShape(insertShape)}`) }) }}</span></OuiHint></div>
        <SelectButton :model-value="pocketShape" :options="pocketShapes" option-label="label" option-value="value" :allow-empty="false" class="em-cuts" :disabled="inSlot"
                      aria-labelledby="cut-l" aria-describedby="cut-help" data-test="pocket-shape" fluid @update:model-value="choosePocketShape($event)">
          <template #option="{ option }"><span class="em-cut" :data-test="`cut-${option.value}`"><OuiIcon :icon="option.icon" :size="16" />{{ option.label }}</span></template>
        </SelectButton>
        <!-- Why the picker is off is said under it; what it does, when it is on, is behind the (i). -->
        <span v-if="inSlot" id="cut-help" class="oui-meta" data-test="pocket-shape-slot">{{ t('form.pocketShapeSlot') }}</span>
      </div>

      <div class="oui-field">
        <div class="em-labelled"><label id="mode-l">{{ t('form.mode') }}</label>
          <OuiHint v-if="!block" :label="t('form.mode')"><span id="em-mode-note">{{ t(s.mode === 'embedded' ? 'mode.embeddedHelp' : 'mode.openHelp') }}</span></OuiHint></div>
        <SelectButton v-model="s.mode" :options="modes" option-label="label" option-value="value" option-disabled="disabled" :allow-empty="false"
                      aria-labelledby="mode-l" :aria-describedby="block ? (blockSaidAbove ? 'em-blocks' : 'em-mode-note') : 'em-mode-note'" data-test="mode" fluid />
        <span v-if="block && !blockSaidAbove" id="em-mode-note" class="oui-meta em-warn" data-test="embedded-block">{{ t('mode.blocked', { reason: tMaybe(`block.${block}`, block) }) }}</span>
      </div>

      <div v-if="insertKind === 'magnet'" class="oui-field">
        <label id="pol-l">{{ t('form.polarity') }}</label>
        <SelectButton v-model="s.polarity" :options="polarities" option-label="label" option-value="value" :allow-empty="false"
                      aria-labelledby="pol-l" data-test="polarity" fluid />
      </div>

      <div class="em-two">
        <div class="oui-field"><label for="f-spin">{{ t('form.spin') }}</label>
          <InputNumber :locale="locale" v-model="s.spin" input-id="f-spin" :min="-360" :max="360" suffix=" °" placeholder="0 °" fluid /></div>
        <div class="oui-field"><label for="f-cover">{{ t('form.cover') }}</label>
          <InputNumber v-decimal :locale="locale" v-model="s.cover" input-id="f-cover" :min="0" :max="10" :max-fraction-digits="2" suffix=" mm" fluid
                       :placeholder="t('form.coverDefault', { mm: fmt.number(coverDefault, 1) })" :title="t('form.coverDefault', { mm: fmt.number(coverDefault, 1) })" :disabled="s.mode !== 'embedded'" /></div>
      </div>

      <div class="em-labelled">
        <label class="em-check" for="f-center"><Checkbox v-model="s.center" binary input-id="f-center" data-test="center" aria-describedby="f-center-help" />{{ t('form.center') }}</label>
        <OuiHint :label="t('form.center')"><span id="f-center-help">{{ t('form.centerHelp') }}</span></OuiHint>
      </div>

      <div class="oui-field">
        <div class="em-labelled">
          <label id="fridge-l">{{ t('form.autoFridge') }}</label>
          <OuiHint :label="t('form.autoFridge')"><span id="fridge-help">{{ t('form.autoFridgeHelp') }}</span></OuiHint>
        </div>
        <div class="em-fridge" role="group" aria-labelledby="fridge-l" aria-describedby="fridge-help" data-test="auto-fridge">
          <Button :label="t('form.autoFridgeAuto')" severity="secondary" size="small" fluid :loading="tracker.isBusy('auto-fridge')" data-test="auto-fridge-auto" @click="autoFridge('auto')" />
          <Button label="1×" severity="secondary" size="small" fluid :disabled="tracker.isBusy('auto-fridge')" data-test="auto-fridge-1" @click="autoFridge(1)" />
          <Button label="2×" severity="secondary" size="small" fluid :disabled="tracker.isBusy('auto-fridge')" data-test="auto-fridge-2" @click="autoFridge(2)" />
          <Button label="4×" severity="secondary" size="small" fluid :disabled="tracker.isBusy('auto-fridge')" data-test="auto-fridge-4" @click="autoFridge(4)" />
        </div>
      </div>
    </div>

    <PlanCard />

    <template #footer>
      <Button v-if="s.selected != null" :label="t('form.done')" severity="secondary" fluid aria-describedby="em-plan-state" data-test="done" @click="selectStaged(null)">
        <template #icon><OuiIcon :icon="check" :size="14" /></template></Button>
      <Button v-else :label="t('plan.add')" severity="secondary" fluid :disabled="!canAdd" aria-describedby="em-plan-state" data-test="add" @click="addStaged">
        <template #icon><OuiIcon :icon="plus" :size="14" /></template></Button>
    </template>
  </OuiPanel>
</template>

<style>
.em-two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--oui-s3); }
.em-two[data-three] { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--oui-s2); }
.em-check { display: flex; align-items: center; gap: var(--oui-s2); min-height: 24px; width: fit-content; }
.oui-field > label.em-check { font-size: inherit; font-weight: inherit; color: inherit; }
/* A label with its (i): the explanation that used to be a line under the control. */
.em-labelled { display: flex; align-items: center; gap: var(--oui-s1); min-width: 0; min-height: 22px; }
.oui-field > .em-labelled > label { font-size: var(--oui-text-sm); font-weight: 600; color: var(--oui-muted); }
.em-opt { display: inline-flex; align-items: center; gap: var(--oui-s2); min-width: 0; }
.em-group { gap: 6px; font-weight: 700; }
.em-custom { display: grid; gap: var(--oui-s3); padding: var(--oui-s3); justify-items: start; }
.em-custom > .em-two { width: 100%; }
.em-warn { color: var(--oui-warning); }
/* Two by two, four in a row where the form has room; each button keeps its icon and its whole name. */
.oui-field:has(> .em-cuts) { container-type: inline-size; }
.em-cuts.p-selectbutton { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
@container (min-width: 460px) { .em-cuts.p-selectbutton { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
.em-cut { display: inline-flex; align-items: center; gap: 6px; min-width: 0; }
.em-fridge { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--oui-s2); }
.em-form .oui-panel-foot { margin-top: auto; }
</style>
