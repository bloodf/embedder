<script setup lang="ts">
import { computed, watch } from 'vue';
import Button from 'primevue/button';
import Select from 'primevue/select';
import SelectButton from 'primevue/selectbutton';
import InputNumber from 'primevue/inputnumber';
import Checkbox from 'primevue/checkbox';
import Icon from './Icon.vue';
import { s, savePreset } from '../app/store';
import { currentObject, replan, selectObject } from '../app/project';
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

const groups = computed(() => groupPresets(s.builtin, s.user).map(g => ({
  label: t(`group.${g.key}`), icon: g.key === 'nfc' ? 'icon/nfc' : g.key === 'magnet' ? 'icon/magnet' : '', items: g.items.map(p => ({ id: p.id, label: presetLabel(p) })) })));
const objects = computed(() => (s.project?.objects ?? []).map(o => ({
  value: o.object, label: o.instance ? t('obj.instance', { name: o.name, n: o.instance + 1 }) : o.name })));
const block = computed(() => embeddedBlock(currentObject(), s.plan));
const modes = computed(() => [
  { value: 'embedded', label: t('mode.embedded'), disabled: !!block.value },
  { value: 'open', label: t('mode.open'), disabled: false }]);
const coverDefault = computed(() => {
  const kind = s.insert.custom?.kind ?? [...s.builtin, ...s.user].find(p => p.id === s.insert.preset)?.kind ?? 'magnet';
  return (kind === 'nfc' ? s.settings?.cover_nfc : s.settings?.cover_magnet) ?? 1;
});
const kinds = computed(() => [{ value: 'magnet', label: t('kind.magnet') }, { value: 'nfc', label: t('kind.nfc') }]);
const shapes = computed(() => [{ value: 'disc', label: t('shape.disc') }, { value: 'block', label: t('shape.block') }]);

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
  <section class="em-card em-form" aria-labelledby="form-h">
    <h2 id="form-h">{{ t('form.title') }}</h2>
    <div class="oui-field">
      <label id="obj-l">{{ t('form.object') }}</label>
      <Select :model-value="s.object" :options="objects" option-label="label" option-value="value" aria-labelledby="obj-l" data-test="object"
              @update:model-value="selectObject($event)" />
    </div>

    <div class="oui-field">
      <label id="ins-l">{{ t('form.insert') }}</label>
      <Select v-if="!s.insert.custom" :model-value="s.insert.preset" :options="groups" option-group-label="label" option-group-children="items"
              option-label="label" option-value="id" aria-labelledby="ins-l" data-test="preset"
              @update:model-value="s.insert = { preset: $event, custom: null }">
        <template #optiongroup="{ option }"><span class="em-group"><Icon v-if="option.icon" :name="option.icon" />{{ option.label }}</span></template>
      </Select>
      <span class="em-row"><Checkbox :model-value="!!s.insert.custom" binary input-id="f-custom" data-test="custom" @update:model-value="setCustom($event)" />
        <label for="f-custom">{{ t('form.custom') }}</label></span>
    </div>

    <div v-if="s.insert.custom" class="em-dims" data-test="custom-dims">
      <label id="k-l">{{ t('form.kind') }}</label>
      <Select :model-value="s.insert.custom.kind" :options="kinds" option-label="label" option-value="value" aria-labelledby="k-l" @update:model-value="setDim('kind', $event)" />
      <label id="sh-l">{{ t('form.shape') }}</label>
      <Select :model-value="s.insert.custom.shape" :options="shapes" option-label="label" option-value="value" aria-labelledby="sh-l" @update:model-value="setDim('shape', $event)" />
      <template v-if="s.insert.custom.shape === 'disc'">
        <label for="f-d">{{ t('form.d') }}</label>
        <InputNumber input-id="f-d" :model-value="s.insert.custom.d" :min="0.1" :max="300" :max-fraction-digits="2" suffix=" mm" @update:model-value="setDim('d', $event)" />
      </template>
      <template v-else>
        <label for="f-l">{{ t('form.l') }}</label>
        <InputNumber input-id="f-l" :model-value="s.insert.custom.l" :min="0.1" :max="300" :max-fraction-digits="2" suffix=" mm" @update:model-value="setDim('l', $event)" />
        <label for="f-w">{{ t('form.w') }}</label>
        <InputNumber input-id="f-w" :model-value="s.insert.custom.w" :min="0.1" :max="300" :max-fraction-digits="2" suffix=" mm" @update:model-value="setDim('w', $event)" />
      </template>
      <label for="f-t">{{ t('form.t') }}</label>
      <InputNumber input-id="f-t" :model-value="s.insert.custom.t" :min="0.1" :max="300" :max-fraction-digits="2" suffix=" mm" @update:model-value="setDim('t', $event)" />
      <span /><Button severity="secondary" outlined :label="t('preset.saveAs')" data-test="save-preset" @click="saveAsPreset" />
    </div>

    <div class="oui-field">
      <label id="mode-l">{{ t('form.mode') }}</label>
      <SelectButton v-model="s.mode" :options="modes" option-label="label" option-value="value" option-disabled="disabled" :allow-empty="false"
                    aria-labelledby="mode-l" data-test="mode" />
      <span v-if="block" class="oui-meta em-warn" data-test="embedded-block">{{ t('mode.blocked', { reason: tMaybe(`block.${block}`, block) }) }}</span>
      <span v-else class="oui-meta">{{ t(s.mode === 'embedded' ? 'mode.embeddedHelp' : 'mode.openHelp') }}</span>
    </div>

    <div class="em-dims">
      <label for="f-spin">{{ t('form.spin') }}</label>
      <InputNumber v-model="s.spin" input-id="f-spin" :min="-360" :max="360" suffix="°" placeholder="0°" />
      <label for="f-cover">{{ t('form.cover') }}</label>
      <InputNumber v-model="s.cover" input-id="f-cover" :min="0" :max="10" :max-fraction-digits="2" suffix=" mm"
                   :placeholder="t('form.coverDefault', { mm: fmt.number(coverDefault, 1) })" :disabled="s.mode !== 'embedded'" />
    </div>
    <div class="oui-field">
      <span class="em-row"><Checkbox v-model="s.center" binary input-id="f-center" data-test="center" aria-describedby="f-center-help" />
        <label for="f-center">{{ t('form.center') }}</label></span>
      <span id="f-center-help" class="oui-meta">{{ t('form.centerHelp') }}</span>
    </div>
  </section>
</template>

<style scoped>
.em-form { display: grid; gap: 12px; }
.em-form > h2 { margin: 0; }
.em-dims { display: grid; grid-template-columns: minmax(100px, auto) minmax(0, 1fr); gap: 8px 12px; align-items: center; }
.em-group { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; }
</style>
