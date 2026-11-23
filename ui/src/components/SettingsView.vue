<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import Button from 'primevue/button';
import Select from 'primevue/select';
import InputNumber from 'primevue/inputnumber';
import { OuiEmpty, OuiFormRow, OuiFormSection, OuiIcon, OuiStatus } from '@orca-plugins/ui-foundation/src/components';
import SettingsPages from './SettingsPages.vue';
import { files, info, insert, languages, magnet, rfid, ruler, save as saveIcon, tag, trash } from '@orca-plugins/ui-foundation/src/icons';
import { s, saveSettings, deletePreset, tracker } from '../app/store';
import { replanStaged } from '../app/project';
import { ask } from '../core/dialog';
import { t, tn, langPref, setLangPref, autoLocale, fmt, locale } from '../core/i18n';
import { vDecimal } from '../core/decimal';
import { LOCALES, type LangPref } from '../core/i18n-core';
import type { CopiesCleared, CopiesStatus, FridgeSurface, MagnetGrade, Preset } from '../app/types';

type Knob = 'xy_clearance' | 'z_clearance' | 'cover_magnet' | 'cover_nfc';
const knobs: { key: Knob; max: number }[] = [
  { key: 'xy_clearance', max: 1 }, { key: 'z_clearance', max: 1 }, { key: 'cover_magnet', max: 10 }, { key: 'cover_nfc', max: 10 }];
const form = reactive<{ xy_clearance: number | null; z_clearance: number | null; cover_magnet: number | null; cover_nfc: number | null; magnet_grade: MagnetGrade; fridge_surface: FridgeSurface }>({
  xy_clearance: null, z_clearance: null, cover_magnet: null, cover_nfc: null, magnet_grade: 'N35', fridge_surface: 'steel' });
const gradeOptions = computed(() => (['N35', 'N42', 'N52', 'ferrite'] as MagnetGrade[]).map(value => ({ value, label: t(`grade.${value}`) })));
const surfaceOptions = computed(() => (['steel', 'stainless', 'board'] as FridgeSurface[]).map(value => ({ value, label: t(`surface.${value}`) })));
function reset() {
  const v = s.settings;
  if (!v) return;
  knobs.forEach(k => { form[k.key] = v[k.key]; });
  form.magnet_grade = v.magnet_grade ?? 'N35';
  form.fridge_surface = v.fridge_surface ?? 'steel';
}
watch(() => s.settings, reset, { immediate: true });
const changed = computed(() => {
  if (!s.settings) return [];
  const out: (Knob | 'magnet_grade' | 'fridge_surface')[] = knobs.filter(k => form[k.key] !== s.settings?.[k.key]).map(k => k.key);
  if (form.magnet_grade !== (s.settings.magnet_grade ?? 'N35')) out.push('magnet_grade');
  if (form.fridge_surface !== (s.settings.fridge_surface ?? 'steel')) out.push('fridge_surface');
  return out;
});
const dirty = computed(() => changed.value.length > 0);
const valid = computed(() => knobs.every(k => form[k.key] != null));

const sections = computed(() => [
  { id: 'set-fit', label: t('settings.title'), icon: ruler, state: valid.value ? undefined : 'error' as const },
  { id: 'set-fridge', label: t('settings.fridge'), icon: magnet },
  { id: 'set-presets', label: t('settings.presets'), icon: tag },
  { id: 'set-copies', label: t('copies.title'), icon: files },
  { id: 'set-language', label: t('lang.title'), icon: languages },
  { id: 'set-about', label: t('about.title'), icon: info },
]);
const langOptions = computed(() => [
  { value: 'auto', label: t('lang.auto', { current: t(`lang.${autoLocale.value}`) }) },
  ...LOCALES.map(value => ({ value, label: t(`lang.${value}`) }))]);

async function save() {
  if (!valid.value) return;
  const payload = { ...Object.fromEntries(knobs.map(k => [k.key, form[k.key]])), magnet_grade: form.magnet_grade, fridge_surface: form.fridge_surface };
  if (await saveSettings(payload)) await replanStaged();
}
const dims = (p: Preset) => [p.d ?? p.l, ...(p.shape === 'block' ? [p.w] : []), p.t].map(v => fmt.number(v ?? 0, 2)).join(' × ');
// Old applied copies in the plugin folder: asked each time the tab opens, since an Apply may have pruned some.
const copies = ref<CopiesStatus | null>(null);
const size = (b: number) => (b < 1024 * 1024 ? `${fmt.number(b / 1024, 0)} KB` : `${fmt.number(b / (1024 * 1024), 1)} MB`);
async function loadCopies() {
  const r = await tracker.run<CopiesStatus>({ key: 'copies', label: t('act.copies'), cmd: 'copies.status' });
  if (r.ok) copies.value = r.result;
}
async function clearCopies() {
  const c = copies.value;
  if (!c?.count) return;
  if (!(await ask({ title: t('copies.clearTitle'), text: tn('copies.clearText', c.count, { size: size(c.bytes) }), yes: t('copies.clear'), danger: true }))) return;
  const r = await tracker.run<CopiesCleared>({ key: 'copies-clear', label: t('act.copiesClear'), cmd: 'copies.clear' });
  if (!r.ok) return;
  copies.value = r.result;
  if (r.result.removed) tracker.notify('success', tn('copies.cleared', r.result.removed, { size: size(r.result.freed) }));
  if (r.result.failed) tracker.notify('error', tn('copies.failed', r.result.failed));
}
watch(() => s.tab, tab => { if (tab === 'settings') void loadCopies(); }, { immediate: true });

async function remove(p: Preset) {
  if (await ask({ title: t('preset.deleteTitle'), text: t('preset.deleteText', { name: p.name }), yes: t('preset.delete'), danger: true })) {
    await deletePreset(p.id);
    await replanStaged();
  }
}
</script>

<template>
  <SettingsPages class="em-settings" :sections="sections" :nav-label="t('settings.nav')" :back-label="t('common.goBack')" :error-label="t('settings.hasError')">
    <div class="oui-stack">
      <OuiFormSection id="set-fit" :icon="ruler" :title="t('settings.title')" :description="t('settings.help')">
        <form id="em-settings-form" class="em-setform" data-test="settings-form" @submit.prevent="save">
          <OuiFormRow v-for="k in knobs" :key="k.key" :label="t(`settings.${k.key}`)" :for="'set-' + k.key">
            <InputNumber v-decimal :locale="locale" v-model="form[k.key]" :input-id="'set-' + k.key" :min="0" :max="k.max" :min-fraction-digits="1" :max-fraction-digits="2" :step="0.1" suffix=" mm" />
          </OuiFormRow>
        </form>
      </OuiFormSection>

      <OuiFormSection id="set-fridge" :icon="magnet" :title="t('settings.fridge')" :description="t('settings.fridgeHelp')">
        <div class="em-setform">
          <OuiFormRow :label="t('settings.magnet_grade')" for="set-magnet_grade">
            <Select v-model="form.magnet_grade" input-id="set-magnet_grade" :options="gradeOptions" option-label="label" option-value="value" data-test="magnet-grade" />
          </OuiFormRow>
          <OuiFormRow :label="t('settings.fridge_surface')" for="set-fridge_surface">
            <Select v-model="form.fridge_surface" input-id="set-fridge_surface" :options="surfaceOptions" option-label="label" option-value="value" data-test="fridge-surface" />
          </OuiFormRow>
        </div>
      </OuiFormSection>

      <OuiFormSection id="set-presets" :icon="tag" :title="t('settings.presets')">
        <template v-if="s.user.length" #status><span class="oui-chip oui-num">{{ s.user.length }}</span></template>
        <OuiEmpty v-if="!s.user.length" compact :icon="tag" :title="t('settings.presetsEmpty')" data-test="presets-empty" />
        <ul v-else class="em-rows" data-test="user-presets">
          <li v-for="p in s.user" :key="p.id">
            <span class="em-kind em-kind-lg" :data-kind="p.kind"><OuiIcon :icon="p.kind === 'nfc' ? rfid : insert" :size="16" /></span>
            <div class="em-row-id"><p class="oui-strong">{{ p.name }}</p><p class="oui-meta oui-num">{{ t(`kind.${p.kind}`) }} · {{ dims(p) }} mm</p></div>
            <Button outlined severity="danger" size="small" :aria-label="t('preset.deleteNamed', { name: p.name })" @click="remove(p)"><template #icon><OuiIcon :icon="trash" :size="14" /></template></Button>
          </li>
        </ul>
      </OuiFormSection>
    </div>

    <div class="oui-stack">
      <OuiFormSection id="set-copies" :icon="files" tone="neutral" :title="t('copies.title')" :description="t('copies.help')" data-test="copies">
        <div class="em-copies">
          <span role="status" data-test="copies-status">{{ copies?.count ? tn('copies.status', copies.count, { size: size(copies.bytes) }) : copies ? t('copies.none') : '' }}</span>
          <Button :label="t('copies.clear')" severity="danger" outlined :disabled="!copies?.count" :loading="tracker.isBusy('copies-clear')" data-test="copies-clear" @click="clearCopies">
            <template #icon><OuiIcon :icon="trash" :size="14" /></template></Button>
        </div>
      </OuiFormSection>

      <OuiFormSection id="set-language" :icon="languages" tone="neutral" :title="t('lang.title')">
        <OuiFormRow :label="t('lang.label')">
          <Select :model-value="langPref" :options="langOptions" option-label="label" option-value="value" :aria-label="t('lang.label')" data-test="lang"
                  @update:model-value="setLangPref($event as LangPref)" />
        </OuiFormRow>
      </OuiFormSection>

      <OuiFormSection id="set-about" :icon="info" tone="neutral" :title="t('about.title')" data-test="about">
        <OuiFormRow :label="t('about.version')"><span class="oui-num oui-strong" data-test="version">{{ s.version || '—' }}</span></OuiFormRow>
      </OuiFormSection>
    </div>

    <template #footer>
      <span role="status" class="em-unsaved"><OuiStatus v-if="dirty" state="pending">{{ t('settings.unsaved') }}</OuiStatus></span>
      <span v-if="dirty" class="oui-meta oui-truncate">{{ changed.map(k => t(`settings.${k}`)).join(', ') }}</span>
      <span class="oui-spacer" />
      <Button :label="t('settings.discard')" severity="secondary" text :disabled="!dirty" data-test="settings-discard" @click="reset" />
      <Button :label="t('common.save')" type="submit" form="em-settings-form" :disabled="!s.settings || !dirty || !valid" :loading="tracker.isBusy('settings')" data-test="settings-save">
        <template #icon><OuiIcon :icon="saveIcon" :size="14" /></template></Button>
    </template>
  </SettingsPages>
</template>

<style>
/* The settings page brings its own padding; it sits edge to edge in the page. */
.em-settings { margin: calc(-1 * var(--oui-s3)) calc(-1 * var(--oui-s4)) calc(-1 * var(--oui-s6)); }
.em-setform > * + * { border-top: 1px solid var(--oui-border); }
.em-copies { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--oui-s2) var(--oui-s4); padding: var(--oui-s3) var(--oui-s4); }
/* The live region stays rendered so "Unsaved changes" is announced; empty, it takes no room (the negative margin
   cancels the footer's gap). Not :empty, which Vue's anchor comment defeats. */
.em-unsaved:not(:has(*)) { width: 0; margin-inline-end: calc(-1 * var(--oui-s3)); overflow: hidden; }
.em-settings .em-rows > li:last-child { border-bottom: 0; }
</style>
