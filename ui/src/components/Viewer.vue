<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import Button from 'primevue/button';
import Icon from './Icon.vue';
import { s } from '../app/store';
import { currentObject, meshesOf, placeAt } from '../app/project';
import { createScene, type SceneApi } from '../core/scene';
import { t } from '../core/i18n';

// three.js objects stay in this plain variable, never in Vue state.
let scene: SceneApi | null = null;
const host = ref<HTMLElement | null>(null);

function showParts() {
  const obj = currentObject();
  if (!scene || !obj || s.mesh.state !== 'ready') return;
  const normal = new Set(obj.parts.filter(p => p.subtype === 'normal_part').map(p => p.part));
  scene.setParts(meshesOf(obj.object), part => normal.has(part));
}
function showPockets() {
  scene?.setPockets(s.plan?.preview ?? null, s.staged.flatMap(x => (x.plan.preview ? [x.plan.preview] : [])));
}

onMounted(() => {
  if (!host.value) return;
  try {
    scene = createScene(host.value, hit => { void placeAt(hit); });
  } catch {
    s.webgl = false;   // the probe passed but this context did not: fall back to the numeric form
    return;
  }
  showParts();
  showPockets();
});
watch(() => [s.mesh.version, s.object], showParts);
watch(() => [s.plan, s.staged], showPockets);
onBeforeUnmount(() => { scene?.dispose(); scene = null; });
</script>

<template>
  <section class="em-card em-viewer" data-test="viewer" :aria-label="t('view.label')">
    <div class="em-viewer-bar">
      <span class="oui-meta">{{ s.mesh.state === 'loading' ? t('view.loading', { done: s.mesh.done, total: s.mesh.total }) : t('view.hint') }}</span>
      <Button severity="secondary" outlined size="small" :aria-label="t('view.fit')" :title="t('view.fit')" @click="scene?.fit()">
        <Icon name="icon/fit-view" /><span>{{ t('view.fit') }}</span></Button>
    </div>
    <div ref="host" class="em-viewer-host" />
  </section>
</template>

<style scoped>
.em-viewer { display: flex; flex-direction: column; gap: 8px; min-height: 420px; }
.em-viewer-bar { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.em-viewer-host { flex: 1; min-height: 360px; border-radius: 6px; overflow: hidden; background: var(--oui-background); cursor: crosshair; touch-action: none; }
</style>
