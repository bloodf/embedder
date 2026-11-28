<script setup lang="ts">
import { computed } from 'vue';
import Button from 'primevue/button';
import ProgressBar from 'primevue/progressbar';
import { OuiBanner, OuiEmpty, OuiIcon, OuiPanel } from '@orca-plugins/ui-foundation/src/components';
import { box, folder, warning } from '@orca-plugins/ui-foundation/src/icons';
import insertArt from '../assets/embedder-insert.webp';
import Viewer from './Viewer.vue';
import PlaceFallback from './PlaceFallback.vue';
import PocketForm from './PocketForm.vue';
import PocketList from './PocketList.vue';
import ResultCard from './ResultCard.vue';
import { s } from '../app/store';
import { loadProject } from '../app/project';
import { t, tMaybe, listOf } from '../core/i18n';

const percent = computed(() => (s.loading?.total ? Math.round((100 * s.loading.done) / s.loading.total) : 0));
const blocks = computed(() => (s.project?.blocks ?? []).map(code => tMaybe(`block.${code}`, code).replace(/\.$/, '')));   // each is a clause of one sentence
// The three panels work as one screen (two and three columns): they share the height the page has left under the bar
// and whatever banner shows above them, so nothing a banner pushes down is cut by the window edge.
const working = computed(() => !!s.project && !s.loading && !s.result && s.project.objects.length > 0);
</script>

<template>
  <div class="em-work" :data-fit="working || undefined">
    <!-- Mounted whatever the panel below, so it follows its condition (the project's blocks) through a load: a block
         that goes and comes back shows again; one that holds stays closed. Out of sight while a project loads. -->
    <OuiBanner v-show="!s.loading" :show="blocks.length > 0" id="em-blocks" tone="warn" :title="t('block.title')" data-test="blocks"
      dismissible :dismiss-key="'blocks:' + s.project?.job + ':' + s.project?.blocks.join(',')" :close-label="t('common.close')">{{ t('block.body', { reasons: listOf(blocks) }) }}</OuiBanner>

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
          <!-- Not while the plugin has not answered: the banner above says why and has the way out. -->
          <Button :label="t('load.button')" :disabled="!!s.error" :aria-describedby="s.error ? 'em-hello-error' : undefined" data-test="load" @click="loadProject"><template #icon><OuiIcon :icon="folder" :size="14" /></template></Button>
        </template>
      </OuiEmpty>
      <template v-if="s.webgl === false" #footer>
        <p class="oui-meta em-note" data-test="no3d-hint"><OuiIcon :icon="warning" tone="warn" :size="14" />{{ t('embed.no3d') }}</p>
      </template>
    </OuiPanel>

    <template v-else>
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
  </div>
</template>

<style>
/* One panel alone on the page (no project yet, loading, nothing on the plate): centred, as wide as its sentence needs. */
.em-solo { justify-self: center; width: min(100%, 560px); margin-top: var(--oui-s8); }
.em-solo .oui-empty { padding-block: var(--oui-s8); }
.em-solo .oui-empty-image { width: 176px; height: 176px; }
.em-loadbar { width: 240px; max-width: 100%; height: 8px; }

.em-work { display: flex; flex-direction: column; gap: var(--oui-s3); min-width: 0; }
.em-work > .em-solo, .em-work > .em-result { align-self: center; }

/* Form, 3D view, list. One column: the page scrolls. From two columns on they are one screen: the page is as tall as
   the window, this block takes what the bar and the banners above leave (it is stretched by the page's grid, no
   height is worked out here), and each panel scrolls inside itself and keeps its footer, so the pocket in hand, Add
   pocket and Apply are always in sight. Two columns: the form beside the 3D view with the list under the view. Three
   columns when there is room. A short window keeps a workable height and the page scrolls. */
.em-grid { display: grid; gap: var(--oui-s3); grid-template-columns: minmax(0, 1fr); align-items: start; }
.em-stage-panel { height: 440px; }
@container oui-page (min-width: 860px) {
  .em-work[data-fit] { min-height: 480px; }
  .em-grid { flex: 1 1 0; min-height: 0; align-items: stretch; grid-template-columns: 320px minmax(0, 1fr); grid-template-rows: minmax(0, 11fr) minmax(0, 9fr);
    grid-template-areas: 'form stage' 'form list'; }
  .em-form { grid-area: form; }
  .em-stage-panel { grid-area: stage; height: auto; }
  .em-list { grid-area: list; }
  .em-grid > .oui-panel { min-height: 0; }
  .em-grid > :is(.em-form, .em-list) > .oui-panel-body { flex: 1 1 0; min-height: 0; overflow-y: auto; overscroll-behavior: contain; }
  /* Without the 3D view the place form is as tall as its one row, and the list takes the rest of the column. */
  .em-grid:has(> .em-fallback) { grid-template-rows: auto minmax(0, 1fr); }
}
@container oui-page (min-width: 1200px) {   /* 1280 px windows keep three columns beside a classic scrollbar */
  .em-grid, .em-grid:has(> .em-fallback) { grid-template-columns: 320px minmax(0, 1fr) 380px; grid-template-rows: minmax(0, 1fr); grid-template-areas: 'form stage list'; }
}
</style>
