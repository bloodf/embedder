<script setup lang="ts">
import { computed, onBeforeUnmount } from 'vue';
import Button from 'primevue/button';
import { OuiAppBar, OuiIcon, OuiStatus, type OuiState } from '../shared/src/components';
import { magnet, refresh, settings } from '../shared/src/icons';
import ConfirmDialog from './components/ConfirmDialog.vue';
import NoticeArea from './components/NoticeArea.vue';
import EmbedView from './components/EmbedView.vue';
import SettingsView from './components/SettingsView.vue';
import { s, start } from './app/store';
import { loadProject } from './app/project';
import { t, tn } from './core/i18n';

const stop = start();
onBeforeUnmount(stop);
const tabs = computed(() => [
  { value: 'embed', label: t('nav.embed'), icon: magnet },
  { value: 'settings', label: t('nav.settings'), icon: settings },
]);
// The page's one state: what the plugin holds right now. Nothing else on the page repeats or contradicts it.
const state = computed<{ kind: OuiState; label: string }>(() =>
  s.error ? { kind: 'error', label: t('state.error') }
  : s.loading ? { kind: 'busy', label: t('state.loading') }
  : s.result ? { kind: 'ok', label: t('state.applied') }
  : s.project ? { kind: 'ok', label: t('state.loaded') }
  : { kind: 'idle', label: t('state.none') });
</script>

<template>
  <OuiAppBar v-model="s.tab" :name="t('app.brand')" :tabs="tabs" :tabs-label="t('nav.label')">
    <template #mark>
      <!-- The brand kit's micro mark (assets/embedder-micro-24.svg): the bars take the band colour, the insert its ink. -->
      <svg viewBox="0 0 24 24" fill="currentColor"><title>{{ t('about.text', { version: s.version || '—' }) }}</title>
        <rect x="3" y="3" width="18" height="3" rx=".5" /><rect x="3" y="18" width="18" height="3" rx=".5" />
        <rect x="3" y="8" width="4" height="3" rx=".5" /><rect x="17" y="8" width="4" height="3" rx=".5" />
        <rect x="3" y="13" width="4" height="3" rx=".5" /><rect x="17" y="13" width="4" height="3" rx=".5" />
        <circle class="em-mark-insert" cx="12" cy="12" r="3" /></svg>
    </template>
    <template #status>
      <OuiStatus :state="state.kind" data-test="state">{{ state.label }}</OuiStatus>
      <span v-if="s.project" class="oui-truncate" data-test="project">
        <span data-test="project-name">{{ s.project.name }}</span> · {{ t('load.plate', { plate: s.project.plate, plates: s.project.plates }) }} · {{ tn('load.objects', s.project.objects.length) }}
      </span>
    </template>
    <template v-if="s.project && !s.loading" #actions>
      <Button :label="t('load.again')" severity="secondary" size="small" data-test="reload" @click="loadProject">
        <template #icon><OuiIcon :icon="refresh" :size="14" /></template></Button>
    </template>
  </OuiAppBar>

  <main class="oui-page em">
    <NoticeArea />
    <div v-show="s.tab === 'embed'" id="em-view-embed" class="em-view" role="tabpanel" aria-labelledby="oui-tab-embed"><EmbedView /></div>
    <div v-show="s.tab === 'settings'" id="em-view-settings" class="em-view" role="tabpanel" aria-labelledby="oui-tab-settings"><SettingsView /></div>
  </main>
  <ConfirmDialog />
</template>

<style>
/* Embedder's brand colours for the two kinds of insert (assets/asset-manifest.json, palette.magnet and palette.nfc).
   On the root, where the 3D view reads them. */
:root { --em-magnet: #8c4b08; --em-nfc: #6541a6; --em-ink: #202731; }
:root.orca-dark { --em-magnet: #f2bc7a; --em-nfc: #c7b5ff; }
html, body, #app { min-height: 100%; }
/* A classic scrollbar (Windows) appearing when the page grows must not narrow the page and flip the Embed layout. */
html { scrollbar-gutter: stable; }
.em-mark-insert { fill: var(--em-ink); }
.em-view { display: grid; gap: var(--oui-s3); min-width: 0; }

/* Shared by the Embed panels and Settings: what kind of insert a thing is, as a dot (in a line of text) or a tile (on a row). */
.em-kind { flex: none; display: inline-grid; place-items: center; width: 10px; height: 10px; border-radius: 50%; color: var(--em-magnet); background: currentColor; }
.em-kind[data-kind='nfc'] { color: var(--em-nfc); border-radius: 2px; }
.em-kind.em-kind-lg { width: 28px; height: 28px; border-radius: var(--oui-radius); background: color-mix(in srgb, currentColor 16%, transparent); }
.em-rows { list-style: none; padding: 0; }
.em-rows > li { display: flex; align-items: center; gap: var(--oui-s3); min-height: 52px; padding: var(--oui-s2) var(--oui-s2) var(--oui-s2) var(--oui-s4); border-bottom: 1px solid var(--oui-border); }
.em-row-id { flex: 1 1 0; display: grid; gap: 1px; min-width: 0; }
.em-row-id > .oui-strong { overflow-wrap: anywhere; }
.em-note { display: flex; align-items: flex-start; gap: 6px; }
.em-note > .oui-icon { margin-top: 1px; }
</style>
