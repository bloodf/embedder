<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import Button from 'primevue/button';
import Select from 'primevue/select';
import InputNumber from 'primevue/inputnumber';
import { OuiEmpty, OuiFormRow, OuiFormSection, OuiIcon, OuiStatus } from '@orca-plugins/ui-foundation/src/components';
import { files, insert, refresh, rfid, ruler, settings as cog, tag, trash } from '@orca-plugins/ui-foundation/src/icons';
import { s, saveSettings, deletePreset, tracker } from '../app/store';
import { replanStaged } from '../app/project';
import { ask } from '../core/dialog';
import { t, tn, langPref, setLangPref, autoLocale, fmt, locale, sizeLabel } from '../core/i18n';
import { vDecimal } from '../core/decimal';
import { LOCALES, type LangPref } from '../core/i18n-core';
import type { CopiesCleared, CopiesStatus, FridgeSurface, MagnetGrade, Preset } from '../app/types';

// Ten controls, one page: no list of sections to pick from. Nothing here has a Save button: a change is saved as it
// is made (a moment after the last one), and the line along the bottom says so, or that saving failed, with Retry.
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
const values = () => ({ ...Object.fromEntries(knobs.map(k => [k.key, form[k.key]])), magnet_grade: form.magnet_grade, fridge_surface: form.fridge_surface });
const dirty = computed(() => !!s.settings && (knobs.some(k => form[k.key] !== s.settings?.[k.key])
  || form.magnet_grade !== (s.settings.magnet_grade ?? 'N35') || form.fridge_surface !== (s.settings.fridge_surface ?? 'steel')));
const valid = computed(() => knobs.every(k => form[k.key] != null));

const SAVE_AFTER_MS = 400;
const status = ref<'' | 'saving' | 'saved' | 'error'>('');
let timer: ReturnType<typeof setTimeout> | undefined;
let saving = false;
/** Save what the form holds now. A change made while a save is out is saved after it, so the last one always lands. */
async function flush() {
  clearTimeout(timer);
  timer = undefined;
  if (saving) return;
  saving = true;
  let sent = false;
  try {
    while (dirty.value && valid.value) {
      status.value = 'saving';
      const was = JSON.stringify(values());
      if (!(await saveSettings(values()))) { status.value = 'error'; return; }
      status.value = 'saved';
      sent = true;
      if (JSON.stringify(values()) === was) reset();   // unchanged meanwhile: show the values as the plugin keeps them
    }
  } finally {
    saving = false;
  }
  if (sent) await replanStaged();   // the pockets on the list are planned with the new clearances
}
watch(form, () => {
  if (!dirty.value) return;
  if (!valid.value) status.value = '';   // not "Saved" beside a value that is missing
  clearTimeout(timer);
  timer = setTimeout(flush, SAVE_AFTER_MS);
});
// Settings that come from the plugin (the first answer, a pocket shape kept) fill the form, unless a change of the
// user's is still on its way out.
watch(() => s.settings, () => { if (!saving && !timer) reset(); }, { immediate: true });
onBeforeUnmount(() => clearTimeout(timer));

const langOptions = computed(() => [
  { value: 'auto', label: t('lang.auto', { current: t(`lang.${autoLocale.value}`) }) },
  ...LOCALES.map(value => ({ value, label: t(`lang.${value}`) }))]);

// Old applied copies in the plugin folder: asked each time the tab opens, since an Apply may have pruned some.
const copies = ref<CopiesStatus | null>(null);
const size = (b: number) => (b < 1024 * 1024 ? `${fmt.number(b / 1024, 0)} KB` : `${fmt.number(b / (1024 * 1024), 1)} MB`);
async function loadCopies() {
  const r = await tracker.run<CopiesStatus>({ key: 'copies', label: t('act.copies'), cmd: 'copies.status', background: true });
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
// While Settings shows, the toasts stack above its status line (the foundation's toast host reads this).
// ponytail: a fixed lift for a one-line bar; measure the bar if it ever holds more than a line.
watch(() => s.tab, tab => {
  if (tab === 'settings') void loadCopies();
  if (tab === 'settings') document.documentElement.style.setProperty('--oui-toast-bottom', '56px');
  else document.documentElement.style.removeProperty('--oui-toast-bottom');
}, { immediate: true });

async function remove(p: Preset) {
  if (await ask({ title: t('preset.deleteTitle'), text: t('preset.deleteText', { name: p.name }), yes: t('preset.delete'), danger: true })) {
    await deletePreset(p.id);
    await replanStaged();
  }
}
</script>

<template>
  <div class="em-settings">
    <div class="em-settings-cols">
      <div class="oui-stack">
        <OuiFormSection :icon="ruler" :title="t('settings.pockets')" :description="t('settings.help')">
          <form class="em-setform" data-test="settings-form" @submit.prevent="flush">
            <OuiFormRow v-for="k in knobs" :key="k.key" :label="t(`settings.${k.key}`)" :for="'set-' + k.key" :error="form[k.key] == null && s.settings ? t('settings.required') : undefined">
              <InputNumber v-decimal :locale="locale" v-model="form[k.key]" :input-id="'set-' + k.key" :min="0" :max="k.max" :min-fraction-digits="1" :max-fraction-digits="2" :step="0.1" suffix=" mm"
                           :invalid="form[k.key] == null && !!s.settings" />
            </OuiFormRow>
            <OuiFormRow :label="t('settings.magnet_grade')" for="set-magnet_grade" :hint="t('settings.fridgeHelp')">
              <Select v-model="form.magnet_grade" input-id="set-magnet_grade" :options="gradeOptions" option-label="label" option-value="value" data-test="magnet-grade" />
            </OuiFormRow>
            <OuiFormRow :label="t('settings.fridge_surface')" for="set-fridge_surface">
              <Select v-model="form.fridge_surface" input-id="set-fridge_surface" :options="surfaceOptions" option-label="label" option-value="value" data-test="fridge-surface" />
            </OuiFormRow>
          </form>
        </OuiFormSection>

        <OuiFormSection :icon="tag" :title="t('settings.presets')">
          <template v-if="s.user.length" #status><span class="oui-chip oui-num">{{ s.user.length }}</span></template>
          <OuiEmpty v-if="!s.user.length" compact :icon="tag" :title="t('settings.presetsEmpty')" data-test="presets-empty" />
          <ul v-else class="em-rows" data-test="user-presets">
            <li v-for="p in s.user" :key="p.id">
              <span class="em-kind em-kind-lg" :data-kind="p.kind"><OuiIcon :icon="p.kind === 'nfc' ? rfid : insert" :size="16" /></span>
              <div class="em-row-id"><p class="oui-strong">{{ p.name }}</p><p class="oui-meta oui-num">{{ t(`kind.${p.kind}`) }} · {{ sizeLabel(p) }}</p></div>
              <Button outlined severity="danger" size="small" :aria-label="t('preset.deleteNamed', { name: p.name })" @click="remove(p)"><template #icon><OuiIcon :icon="trash" :size="14" /></template></Button>
            </li>
          </ul>
        </OuiFormSection>
      </div>

      <div class="oui-stack">
        <OuiFormSection :icon="files" tone="neutral" :title="t('copies.title')" :description="t('copies.help')" data-test="copies">
          <div class="em-copies">
            <span role="status" data-test="copies-status">{{ copies?.count ? tn('copies.status', copies.count, { size: size(copies.bytes) }) : copies ? t('copies.none') : '' }}</span>
            <Button :label="t('copies.clear')" severity="danger" outlined :disabled="!copies?.count" :loading="tracker.isBusy('copies-clear')" data-test="copies-clear" @click="clearCopies">
              <template #icon><OuiIcon :icon="trash" :size="14" /></template></Button>
          </div>
        </OuiFormSection>

        <OuiFormSection :icon="cog" tone="neutral" :title="t('settings.general')" data-test="general">
          <OuiFormRow :label="t('lang.label')">
            <Select :model-value="langPref" :options="langOptions" option-label="label" option-value="value" :aria-label="t('lang.label')" data-test="lang"
                    @update:model-value="setLangPref($event as LangPref)" />
          </OuiFormRow>
          <p class="oui-meta oui-num em-version" data-test="about">{{ t('about.version') }} <span data-test="version">{{ s.version || '—' }}</span></p>
        </OuiFormSection>
      </div>
    </div>

    <footer class="em-savebar" data-test="settings-status">
      <span role="status" class="em-saved">
        <OuiStatus v-if="status === 'saved'" state="ok" variant="plain" data-test="settings-saved">{{ t('settings.saved') }}</OuiStatus>
        <OuiStatus v-else-if="status === 'error'" state="error" variant="plain" data-test="settings-failed">{{ t('settings.saveFailed') }}</OuiStatus>
      </span>
      <Button v-if="status === 'error'" :label="t('common.retry')" severity="secondary" size="small" data-test="settings-retry" @click="flush"><template #icon><OuiIcon :icon="refresh" :size="14" /></template></Button>
      <span class="oui-meta">{{ t('settings.autosave') }}</span>
    </footer>
  </div>
</template>

<style>
/* One page: its sections in two columns where there is room, and one status line along the bottom edge of the window
   (it bleeds through the page's padding, and stays in sight while a long page scrolls). */
.em-settings { display: flex; flex-direction: column; gap: var(--oui-s3); min-width: 0; margin-bottom: calc(-1 * var(--oui-s6)); }
.em-settings-cols { display: grid; gap: var(--oui-s3); grid-template-columns: minmax(0, 1fr); align-items: start; width: 100%; max-width: 1120px; }
@container oui-page (min-width: 1000px) { .em-settings-cols { grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); } }
.em-savebar { position: sticky; bottom: 0; z-index: 5; display: flex; flex-wrap: wrap; align-items: center; gap: var(--oui-s2) var(--oui-s3); min-height: 44px;
  margin: auto calc(-1 * var(--oui-s4)) 0; padding: var(--oui-s2) var(--oui-s4); background: var(--oui-surface); border-top: 1px solid var(--oui-border); }
/* The live region stays rendered so "Saved" is announced; empty, it takes no room. Not :empty, which Vue's anchor
   comment defeats. */
.em-saved:not(:has(*)) { width: 0; margin-inline-end: calc(-1 * var(--oui-s3)); overflow: hidden; }
.em-setform > * + * { border-top: 1px solid var(--oui-border); }
.em-copies { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--oui-s2) var(--oui-s4); padding: var(--oui-s3) var(--oui-s4); }
.em-version { padding: var(--oui-s3) var(--oui-s4); }
.em-settings .em-rows > li:last-child { border-bottom: 0; }
/* foundation-gap: a form row stretches a number or a choice across the whole panel (550 px for "0.35 mm"). */
.em-settings .oui-formrow-control > :where(.p-inputnumber, .p-select) { flex: 0 1 220px; }
</style>
