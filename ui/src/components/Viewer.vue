<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import Button from 'primevue/button';
import { OuiIcon, OuiPanel } from '../../shared/src/components';
import { box, target } from '../../shared/src/icons';
import { s } from '../app/store';
import { currentObject, meshesOf, placeAt } from '../app/project';
import { previewsFor, sizeOf } from '../app/logic';
import { createScene, type SceneApi } from '../core/scene';
import { theme } from '../core/theme';
import { t, fmt } from '../core/i18n';

// three.js objects stay in this plain variable, never in Vue state.
let scene: SceneApi | null = null;
const host = ref<HTMLElement | null>(null);
const object = computed(() => currentObject());
/** "60 × 40 × 8 mm": the object's own size, measured from the meshes the plugin sent. */
const size = computed(() => {
  void s.mesh.version;
  const dims = object.value && s.mesh.state === 'ready' ? sizeOf(meshesOf(object.value.object)) : null;
  return dims ? dims.map(v => fmt.number(v, 1).replace(/[.,]0$/, '')).join(' × ') + ' mm' : '';
});

function showParts(refit = true) {
  const obj = currentObject();
  if (!scene || !obj || s.mesh.state !== 'ready') return;
  const normal = new Set(obj.parts.filter(p => p.subtype === 'normal_part').map(p => p.part));
  scene.setParts(meshesOf(obj.object), part => normal.has(part), refit);
}
function showPockets() {
  scene?.setPockets(s.plan?.preview ?? null, previewsFor(s.staged, s.object));
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
watch(() => [s.mesh.version, s.object], () => showParts());
watch(() => [s.plan, s.staged], showPockets);
// The scene reads its colours from the palette when it builds its materials: build them again in the new theme.
watch(theme, () => { showParts(false); showPockets(); });
onBeforeUnmount(() => { scene?.dispose(); scene = null; });
</script>

<template>
  <OuiPanel class="em-viewer" :title="object?.name ?? t('view.label')" :icon="box" tone="sky" flush data-test="viewer" :aria-label="t('view.label')">
    <template #meta>{{ s.mesh.state === 'loading' ? t('view.loading', { done: s.mesh.done, total: s.mesh.total }) : size }}</template>
    <template #actions>
      <Button :label="t('view.fit')" severity="secondary" text size="small" @click="scene?.fit()"><template #icon><OuiIcon :icon="target" :size="14" /></template></Button>
    </template>
    <div class="em-stage">
      <div ref="host" class="em-stage-host" />
      <p class="oui-meta em-hint">{{ t('view.hint') }}</p>
    </div>
  </OuiPanel>
</template>

<style>
/* The view takes the height its grid cell gives the panel: the canvas is out of flow, so it can never set that height. */
.em-viewer > .oui-panel-body { display: grid; min-height: 0; }
.em-stage { position: relative; min-height: 0; overflow: hidden; background: var(--oui-sky-soft); border-radius: 0 0 var(--oui-radius-lg) var(--oui-radius-lg); }
.em-stage-host { position: absolute; inset: 0; cursor: crosshair; touch-action: none; }
.em-stage-host > canvas { position: absolute; inset: 0; display: block; }
.em-hint { position: absolute; inset: auto var(--oui-s3) var(--oui-s3); text-align: center; pointer-events: none; }
</style>
