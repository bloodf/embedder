<script setup lang="ts">
import { computed } from 'vue';
import Button from 'primevue/button';
import ProgressBar from 'primevue/progressbar';
import { OuiBanner, OuiEmpty, OuiIcon, OuiPanel } from '../../shared/src/components';
import { box, folder, warning } from '../../shared/src/icons';
import insertArt from '../assets/embedder-insert.webp';
import Viewer from './Viewer.vue';
import PlaceFallback from './PlaceFallback.vue';
import PocketForm from './PocketForm.vue';
import PocketList from './PocketList.vue';
import ResultCard from './ResultCard.vue';
import { s } from '../app/store';
import { loadProject } from '../app/project';
import { t, tMaybe } from '../core/i18n';

const percent = computed(() => (s.loading?.total ? Math.round((100 * s.loading.done) / s.loading.total) : 0));
const blocks = computed(() => (s.project?.blocks ?? []).map(code => tMaybe(`block.${code}`, code).replace(/\.$/, '')));   // each is a sentence; one period at the end
</script>

<template>
  <OuiPanel v-if="s.loading" class="em-solo" flush data-test="loading" role="status">
    <OuiEmpty state="loading" :title="s.loading.total ? t('load.progress', { done: s.loading.done, total: s.loading.total }) : t('load.exporting')">
      <template #actions>
        <ProgressBar class="em-loadbar" :mode="s.loading.total ? 'determinate' : 'indeterminate'" :value="percent" :show-value="false" :aria-label="t('load.label')" />
      </template>
    </OuiEmpty>
  </OuiPanel>

  <OuiPanel v-else-if="!s.project" class="em-solo" flush data-test="embed-empty">
    <OuiEmpty :image="insertArt" :title="t('embed.empty.title')" :text="t('embed.empty.body')">
      <template #actions>
        <Button :label="t('load.button')" data-test="load" @click="loadProject"><template #icon><OuiIcon :icon="folder" :size="14" /></template></Button>
      </template>
    </OuiEmpty>
    <template v-if="s.webgl === false" #footer>
      <p class="oui-meta em-note" data-test="no3d-hint"><OuiIcon :icon="warning" tone="warn" :size="14" />{{ t('embed.no3d') }}</p>
    </template>
  </OuiPanel>

  <template v-else>
    <OuiBanner v-if="blocks.length" id="em-blocks" tone="warn" :title="t('block.title')" data-test="blocks">{{ blocks.join('; ') }}.</OuiBanner>
    <ResultCard v-if="s.result" />
    <OuiPanel v-else-if="!s.project.objects.length" class="em-solo" flush data-test="no-objects">
      <OuiEmpty :icon="box" :title="t('load.noObjects')" />
    </OuiPanel>
    <div v-else class="em-grid">
      <PocketForm class="em-form" />
      <Viewer v-if="s.webgl !== false" class="em-stage-panel" />
      <PlaceFallback v-else class="em-stage-panel" />
      <PocketList class="em-list" />
    </div>
  </template>
</template>

<style>
/* One panel alone on the page (no project yet, loading, nothing on the plate): centred, as wide as its sentence needs. */
.em-solo { justify-self: center; width: min(100%, 560px); margin-top: var(--oui-s8); }
.em-solo .oui-empty { padding-block: var(--oui-s8); }
.em-solo .oui-empty-image { width: 176px; height: 176px; }
.em-loadbar { width: 240px; max-width: 100%; height: 8px; }

/* Form, 3D view, list: three columns when there is room (the view takes what is left and stays in sight while the page
   scrolls), form beside the view with the list under them, then one column. */
.em-grid { display: grid; gap: var(--oui-s3); grid-template-columns: minmax(0, 1fr); align-items: start; }
.em-stage-panel { height: 440px; }
@container oui-page (min-width: 860px) {
  .em-grid { grid-template-columns: 320px minmax(0, 1fr); align-items: stretch; }
  .em-stage-panel { height: auto; min-height: 440px; }
  .em-list { grid-column: 1 / -1; }
}
@container oui-page (min-width: 1200px) {   /* 1280 px windows keep three columns beside a classic scrollbar */
  .em-grid { grid-template-columns: 320px minmax(0, 1fr) 380px; min-height: calc(100vh - 88px); }
  .em-stage-panel { position: sticky; top: 64px; align-self: start; height: calc(100vh - 88px); min-height: 360px; }
  .em-list { grid-column: auto; }
}
</style>
