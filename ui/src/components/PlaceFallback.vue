<script setup lang="ts">
import { ref } from 'vue';
import Button from 'primevue/button';
import Select from 'primevue/select';
import Message from 'primevue/message';
import Icon from './Icon.vue';
import { s } from '../app/store';
import { currentObject, meshesOf, placeAt } from '../app/project';
import { centrePick, partMesh } from '../core/pick';
import { t } from '../core/i18n';

// Without WebGL the face is chosen in words: straight down onto the top, or up onto the bottom, at the object's
// centre. The same raycast as a click, with no rendering.
const face = ref<'top' | 'bottom'>('top');
const faces = [{ value: 'top', label: 'place.top' }, { value: 'bottom', label: 'place.bottom' }] as const;

function place() {
  const obj = currentObject();
  if (!obj) return;
  const normal = new Set(obj.parts.filter(p => p.subtype === 'normal_part').map(p => p.part));
  const targets = meshesOf(obj.object).filter(m => normal.has(m.part)).map(m => partMesh(m));
  const hit = centrePick(targets, face.value);
  targets.forEach(m => { m.geometry.dispose(); (m.material as { dispose(): void }).dispose(); });
  void placeAt(hit);
}
</script>

<template>
  <section class="em-card em-fallback" data-test="no3d" aria-labelledby="no3d-h">
    <h2 id="no3d-h">{{ t('no3d.title') }}</h2>
    <Message severity="warn"><Icon name="icon/warning" /> {{ t('embed.no3d') }}</Message>
    <Icon name="spot/no-3d" class="em-spot" />
    <p class="oui-meta">{{ t('no3d.help') }}</p>
    <div class="em-row">
      <label id="face-l">{{ t('place.face') }}</label>
      <Select v-model="face" :options="faces.map(f => ({ value: f.value, label: t(f.label) }))" option-label="label" option-value="value"
              aria-labelledby="face-l" data-test="fallback-face" />
      <Button :label="t('place.button')" :disabled="s.mesh.state !== 'ready'" data-test="fallback-place" @click="place" />
    </div>
  </section>
</template>

<style scoped>
.em-fallback { display: grid; gap: 12px; justify-items: start; }
.em-fallback > h2 { margin: 0; }
</style>
