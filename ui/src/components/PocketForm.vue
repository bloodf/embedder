<script setup lang="ts">
import { computed, watch } from 'vue';
import Button from 'primevue/button';
import Select from 'primevue/select';
import SelectButton from 'primevue/selectbutton';
import InputNumber from 'primevue/inputnumber';
import Checkbox from 'primevue/checkbox';
import { OuiIcon, OuiPanel } from '../../shared/src/components';
import { check, insert, magnet, plus, rfid, save, user } from '../../shared/src/icons';
import PlanCard from './PlanCard.vue';
import { s, savePreset } from '../app/store';
import { addStaged, currentObject, replan, selectObject, selectStaged } from '../app/project';
import { customDims, embeddedBlock, groupPresets } from '../app/logic';
import type { Custom, Preset } from '../app/types';
import { prompt } from '../core/dialog';
import { t, tMaybe, fmt } from '../core/i18n';

const n = (v: number | undefined) => fmt.number(v ?? 0, 1).replace(/[.,]0$/, '');
function presetLabel(p: Preset): string {
  if (!p.builtin) return p.name;
  if (p.id.startsWith('nfc-sticker')) return t('preset.sticker', { d: n(p.d) });
  if (p.id.startsWith('nfc-coin')) return t('preset.coin', { d: n(p.d), t: n(p.t) });
  if (p.id === 'nfc-card') return t('preset.card', { l: n(p.l), w: n(p.w), t: n(p.t) });
  return p.shape === 'disc' ? t('preset.disc', { d: n(p.d), t: n(p.t) }) : t('preset.block', { l: n(p.l), w: n(p.w), t: n(p.t) });
}

const GROUP_ICON = { magnet, nfc: rfid, mine: user };
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
const kinds = computed(() => [{ value: 'magnet', label: t('kind.magnet') }, { value: 'nfc', label: t('kind.nfc') }]);
const shapes = computed(() => [{ value: 'disc', label: t('shape.disc') }, { value: 'block', label: t('shape.block') }]);
const canAdd = computed(() => !!s.plan && !s.plan.blocked && !!s.planArgs);

function setCustom(on: boolean) {
  const fresh: Custom = { kind: 'magnet', shape: 'disc', d: 6, l: 10, w: 5, t: 3 };
  s.insert = on ? { preset: s.insert.preset, custom: fresh } : { preset: s.insert.preset, custom: null };
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
  if (id) s.insert = { preset: id, custom: null };
}

watch(() => [s.insert, s.mode, s.spin, s.cover, s.center], () => { void replan(); });
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
                @update:model-value="s.insert = { preset: $event, custom: null }">
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
            <InputNumber input-id="f-d" :model-value="s.insert.custom.d" :min="0.1" :max="300" :max-fraction-digits="2" suffix=" mm" fluid @update:model-value="setDim('d', $event)" /></div>
          <template v-else>
            <div class="oui-field"><label for="f-l">{{ t('form.l') }}</label>
              <InputNumber input-id="f-l" :model-value="s.insert.custom.l" :min="0.1" :max="300" :max-fraction-digits="2" suffix=" mm" fluid @update:model-value="setDim('l', $event)" /></div>
            <div class="oui-field"><label for="f-w">{{ t('form.w') }}</label>
              <InputNumber input-id="f-w" :model-value="s.insert.custom.w" :min="0.1" :max="300" :max-fraction-digits="2" suffix=" mm" fluid @update:model-value="setDim('w', $event)" /></div>
          </template>
          <div class="oui-field"><label for="f-t">{{ t('form.t') }}</label>
            <InputNumber input-id="f-t" :model-value="s.insert.custom.t" :min="0.1" :max="300" :max-fraction-digits="2" suffix=" mm" fluid @update:model-value="setDim('t', $event)" /></div>
        </div>
        <Button :label="t('preset.saveAs')" severity="secondary" size="small" data-test="save-preset" @click="saveAsPreset"><template #icon><OuiIcon :icon="save" :size="14" /></template></Button>
      </div>

      <div class="oui-field">
        <label id="mode-l">{{ t('form.mode') }}</label>
        <SelectButton v-model="s.mode" :options="modes" option-label="label" option-value="value" option-disabled="disabled" :allow-empty="false"
                      aria-labelledby="mode-l" :aria-describedby="block ? (blockSaidAbove ? 'em-blocks' : 'em-mode-note') : 'em-mode-note'" data-test="mode" fluid />
        <span v-if="block && !blockSaidAbove" id="em-mode-note" class="oui-meta em-warn" data-test="embedded-block">{{ t('mode.blocked', { reason: tMaybe(`block.${block}`, block) }) }}</span>
        <span v-else-if="!block" id="em-mode-note" class="oui-meta">{{ t(s.mode === 'embedded' ? 'mode.embeddedHelp' : 'mode.openHelp') }}</span>
      </div>

      <div class="em-two">
        <div class="oui-field"><label for="f-spin">{{ t('form.spin') }}</label>
          <InputNumber v-model="s.spin" input-id="f-spin" :min="-360" :max="360" suffix=" °" placeholder="0 °" fluid /></div>
        <div class="oui-field"><label for="f-cover">{{ t('form.cover') }}</label>
          <InputNumber v-model="s.cover" input-id="f-cover" :min="0" :max="10" :max-fraction-digits="2" suffix=" mm" fluid
                       :placeholder="t('form.coverDefault', { mm: fmt.number(coverDefault, 1) })" :title="t('form.coverDefault', { mm: fmt.number(coverDefault, 1) })" :disabled="s.mode !== 'embedded'" /></div>
      </div>

      <div class="oui-field">
        <label class="em-check" for="f-center"><Checkbox v-model="s.center" binary input-id="f-center" data-test="center" aria-describedby="f-center-help" />{{ t('form.center') }}</label>
        <span id="f-center-help" class="oui-meta">{{ t('form.centerHelp') }}</span>
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
.em-opt { display: inline-flex; align-items: center; gap: var(--oui-s2); min-width: 0; }
.em-group { gap: 6px; font-weight: 700; }
.em-custom { display: grid; gap: var(--oui-s3); padding: var(--oui-s3); justify-items: start; }
.em-custom > .em-two { width: 100%; }
.em-warn { color: var(--oui-warning); }
.em-form .oui-panel-foot { margin-top: auto; }
</style>
