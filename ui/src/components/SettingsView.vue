<script setup lang="ts">
import { computed, reactive, watch } from 'vue';
import Button from 'primevue/button';
import Select from 'primevue/select';
import InputNumber from 'primevue/inputnumber';
import Icon from './Icon.vue';
import { s, saveSettings, deletePreset, tracker } from '../app/store';
import { ask } from '../core/dialog';
import { t, langPref, setLangPref, autoLocale, fmt } from '../core/i18n';
import type { LangPref } from '../core/i18n-core';
import type { Preset } from '../app/types';

type Knob = 'xy_clearance' | 'z_clearance' | 'cover_magnet' | 'cover_nfc';
const knobs: { key: Knob; max: number }[] = [
  { key: 'xy_clearance', max: 1 }, { key: 'z_clearance', max: 1 }, { key: 'cover_magnet', max: 10 }, { key: 'cover_nfc', max: 10 }];
const form = reactive<Record<Knob, number | null>>({ xy_clearance: null, z_clearance: null, cover_magnet: null, cover_nfc: null });
watch(() => s.settings, v => { if (v) knobs.forEach(k => { form[k.key] = v[k.key]; }); }, { immediate: true });
const dirty = computed(() => !!s.settings && knobs.some(k => form[k.key] !== s.settings?.[k.key]));
const valid = computed(() => knobs.every(k => form[k.key] != null));

const langOptions = computed(() => [
  { value: 'auto', label: t('lang.auto', { current: t(`lang.${autoLocale.value}`) }) },
  { value: 'en', label: t('lang.en') }, { value: 'pt-BR', label: t('lang.pt-BR') }]);

function save() {
  if (!valid.value) return;
  void saveSettings(Object.fromEntries(knobs.map(k => [k.key, form[k.key]])));
}
const dims = (p: Preset) => [p.d ?? p.l, ...(p.shape === 'block' ? [p.w] : []), p.t].map(v => fmt.number(v ?? 0, 2)).join(' × ');
async function remove(p: Preset) {
  if (await ask({ title: t('preset.deleteTitle'), text: t('preset.deleteText', { name: p.name }), yes: t('preset.delete'), danger: true })) await deletePreset(p.id);
}
</script>

<template>
  <div class="em-settings">
    <section class="em-card" aria-labelledby="knobs-h">
      <h2 id="knobs-h">{{ t('settings.title') }}</h2>
      <p class="oui-meta">{{ t('settings.help') }}</p>
      <form class="em-dims" data-test="settings-form" @submit.prevent="save">
        <template v-for="k in knobs" :key="k.key">
          <label :for="'set-' + k.key">{{ t(`settings.${k.key}`) }}</label>
          <InputNumber v-model="form[k.key]" :input-id="'set-' + k.key" :min="0" :max="k.max" :min-fraction-digits="1" :max-fraction-digits="2" :step="0.1" suffix=" mm" />
        </template>
      </form>
      <div class="em-row">
        <Button :label="t('common.save')" :disabled="!s.settings || !dirty || !valid" :loading="tracker.isBusy('settings')" data-test="settings-save" @click="save" />
        <span v-if="dirty" class="oui-meta em-warn" role="status">{{ t('settings.unsaved') }}</span>
      </div>
    </section>

    <section class="em-card" aria-labelledby="mine-h">
      <h2 id="mine-h">{{ t('settings.presets') }}</h2>
      <p v-if="!s.user.length" class="oui-muted" data-test="presets-empty">{{ t('settings.presetsEmpty') }}</p>
      <ul v-else class="em-rows" data-test="user-presets">
        <li v-for="p in s.user" :key="p.id" class="em-item">
          <Icon :name="p.kind === 'nfc' ? 'icon/nfc' : 'icon/magnet'" />
          <span class="em-item-main"><strong>{{ p.name }}</strong> <span class="oui-meta">{{ dims(p) }} mm</span></span>
          <Button text severity="danger" size="small" :aria-label="t('preset.deleteNamed', { name: p.name })" @click="remove(p)"><Icon name="icon/delete" /></Button>
        </li>
      </ul>
    </section>

    <section class="em-card" aria-labelledby="lang-h">
      <h2 id="lang-h">{{ t('lang.title') }}</h2>
      <div class="em-row"><label id="lang-l">{{ t('lang.label') }}</label>
        <Select :model-value="langPref" :options="langOptions" option-label="label" option-value="value" aria-labelledby="lang-l" data-test="lang"
                @update:model-value="setLangPref($event as LangPref)" /></div>
      <p class="oui-meta" data-test="about">{{ t('about.text', { version: s.version || '—' }) }}</p>
    </section>
  </div>
</template>

<style scoped>
.em-settings { display: grid; gap: 16px; max-width: 760px; }
.em-dims { display: grid; grid-template-columns: minmax(160px, 240px) minmax(0, 220px); gap: 8px 12px; align-items: center; margin-bottom: 12px; }
.em-rows { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.em-item { display: flex; align-items: center; gap: 8px; }
.em-item-main { flex: 1; min-width: 0; }
@media (max-width: 640px) { .em-dims { grid-template-columns: minmax(0, 1fr); } }
</style>
