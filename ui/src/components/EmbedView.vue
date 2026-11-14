<script setup lang="ts">
import { computed } from 'vue';
import Button from 'primevue/button';
import Message from 'primevue/message';
import ProgressBar from 'primevue/progressbar';
import Icon from './Icon.vue';
import Viewer from './Viewer.vue';
import PlaceFallback from './PlaceFallback.vue';
import PocketForm from './PocketForm.vue';
import PlanCard from './PlanCard.vue';
import PocketList from './PocketList.vue';
import ResultCard from './ResultCard.vue';
import { s } from '../app/store';
import { loadProject } from '../app/project';
import { t, tMaybe } from '../core/i18n';

const percent = computed(() => (s.loading?.total ? Math.round((100 * s.loading.done) / s.loading.total) : 0));
const blocks = computed(() => (s.project?.blocks ?? []).map(code => tMaybe(`block.${code}`, code)));
</script>

<template>
  <div v-if="s.loading" class="em-card em-loading" data-test="loading" role="status">
    <p>{{ s.loading.total ? t('load.progress', { done: s.loading.done, total: s.loading.total }) : t('load.exporting') }}</p>
    <ProgressBar :mode="s.loading.total ? 'determinate' : 'indeterminate'" :value="percent" :aria-label="t('load.label')" />
  </div>

  <section v-else-if="!s.project" class="em-card em-empty" data-test="embed-empty" aria-labelledby="embed-h">
    <Icon name="spot/no-project" class="em-spot" />
    <h2 id="embed-h">{{ t('embed.empty.title') }}</h2>
    <p>{{ t('embed.empty.body') }}</p>
    <Button data-test="load" @click="loadProject"><Icon name="icon/folder" /><span>{{ t('load.button') }}</span></Button>
    <p v-if="s.webgl === false" class="oui-meta" data-test="no3d-hint"><Icon name="icon/warning" /> {{ t('embed.no3d') }}</p>
  </section>

  <div v-else class="em-work">
    <header class="em-card em-project em-row" data-test="project">
      <strong data-test="project-name">{{ s.project.name }}</strong>
      <span class="oui-meta">{{ t('load.plate', { plate: s.project.plate, plates: s.project.plates }) }}</span>
      <span class="em-spacer" />
      <Button severity="secondary" outlined size="small" data-test="reload" @click="loadProject"><Icon name="icon/folder" /><span>{{ t('load.again') }}</span></Button>
    </header>
    <Message v-if="blocks.length" severity="warn" data-test="blocks">
      <strong>{{ t('block.title') }}</strong>
      <ul class="em-blocks"><li v-for="b in blocks" :key="b">{{ b }}</li></ul>
    </Message>
    <ResultCard v-if="s.result" />
    <p v-else-if="!s.project.objects.length" class="em-card oui-muted" data-test="no-objects">{{ t('load.noObjects') }}</p>
    <div v-else class="em-grid">
      <div class="em-side">
        <PocketForm />
        <PlanCard />
        <PocketList />
      </div>
      <Viewer v-if="s.webgl !== false" />
      <PlaceFallback v-else />
    </div>
  </div>
</template>

<style scoped>
.em-loading { display: grid; gap: 12px; }
.em-empty { display: grid; justify-items: center; gap: 12px; text-align: center; }
.em-empty > * { margin: 0; }
.em-work { display: grid; gap: 16px; }
.em-spacer { flex: 1; }
.em-blocks { margin: 4px 0 0; padding-left: 20px; }
.em-grid { display: grid; grid-template-columns: minmax(300px, 380px) minmax(0, 1fr); gap: 16px; align-items: start; }
.em-side { display: grid; gap: 16px; min-width: 0; }
.em-grid > :last-child { position: sticky; top: 72px; }
@media (max-width: 860px) { .em-grid { grid-template-columns: minmax(0, 1fr); } .em-grid > :last-child { position: static; order: -1; } }
</style>
