<script setup lang="ts">
import { onBeforeUnmount } from 'vue';
import Tabs from 'primevue/tabs';
import TabList from 'primevue/tablist';
import Tab from 'primevue/tab';
import TabPanels from 'primevue/tabpanels';
import TabPanel from 'primevue/tabpanel';
import Icon from './components/Icon.vue';
import ConfirmDialog from './components/ConfirmDialog.vue';
import NoticeArea from './components/NoticeArea.vue';
import EmbedView from './components/EmbedView.vue';
import SettingsView from './components/SettingsView.vue';
import { s, start } from './app/store';
import { t } from './core/i18n';

const stop = start();
onBeforeUnmount(stop);
const sections = [
  { value: 'embed', icon: 'icon/layers', label: 'nav.embed' },
  { value: 'settings', icon: 'icon/settings', label: 'nav.settings' },
] as const;
</script>

<template>
  <Tabs v-model:value="s.tab" class="em-shell">
    <header class="oui-header em-head">
      <span class="em-brand">
        <svg viewBox="0 0 24 24" aria-hidden="true" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M3 10h6M15 10h6M9 10v4a3 3 0 0 0 6 0v-4"/><circle cx="12" cy="13" r="1.5"/><path d="M3 18h18"/></svg>
        <h1>{{ t('app.brand') }}</h1>
      </span>
      <span v-if="s.version" class="oui-meta" data-test="version">{{ s.version }}</span>
      <TabList class="em-nav" :aria-label="t('nav.label')">
        <Tab v-for="sec in sections" :key="sec.value" :value="sec.value" :data-tab="sec.value">
          <Icon :name="sec.icon" /> <span>{{ t(sec.label) }}</span>
        </Tab>
      </TabList>
    </header>
    <main class="em-main">
      <NoticeArea />
      <TabPanels class="em-panels">
        <TabPanel value="embed"><EmbedView /></TabPanel>
        <TabPanel value="settings"><SettingsView /></TabPanel>
      </TabPanels>
    </main>
    <ConfirmDialog />
  </Tabs>
</template>

<style>
html, body, #app { min-height: 100%; }
body { background: var(--oui-background); }
.em-shell { display: flex; flex-direction: column; min-height: 100vh; background: var(--oui-background); }
.em-head { position: sticky; top: 0; z-index: 5; }
.em-brand { display: inline-flex; align-items: center; gap: 8px; }
.em-brand h1 { margin: 0; font-size: 20px; }
.em-nav { margin-left: auto; min-width: 0; }
.em-nav .p-tab { display: inline-flex; gap: 6px; align-items: center; }
.em-main { flex: 1; padding: 16px; display: flex; flex-direction: column; min-width: 0; }
.em-panels.p-tabpanels { padding: 0; background: transparent; }
.em-card { padding: 16px; background: var(--oui-surface); border: 1px solid var(--oui-border); border-radius: 12px; min-width: 0; }
.em-card > h2 { margin: 0 0 12px; }
.em-row { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 12px; }
.em-warn { color: var(--oui-warning); }
.em-card .em-icon.em-spot { width: 160px; height: 120px; color: var(--oui-muted); }
.em-row .em-icon, .p-button .em-icon, .p-message .em-icon { vertical-align: middle; }
@media (max-width: 720px) { .em-main { padding: 12px; } .em-nav { margin-left: 0; width: 100%; overflow-x: auto; } }
</style>
