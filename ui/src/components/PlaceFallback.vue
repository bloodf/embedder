<script setup lang="ts">
import { ref } from 'vue';
import Button from 'primevue/button';
import Select from 'primevue/select';
import { OuiIcon, OuiPanel } from '@orca-plugins/ui-foundation/src/components';
import { box, target } from '@orca-plugins/ui-foundation/src/icons';
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
  <!-- The title says what this is; the one sentence under it how. No tall empty panel around one choice and a button. -->
  <OuiPanel class="em-fallback" :title="t('no3d.title')" :icon="box" tone="sky" data-test="no3d">
    <p id="face-help" class="oui-meta">{{ t('no3d.help') }}</p>
    <div class="em-fallback-row">
      <label id="face-l" class="oui-strong">{{ t('place.face') }}</label>
      <Select v-model="face" :options="faces.map(f => ({ value: f.value, label: t(f.label) }))" option-label="label" option-value="value"
              aria-labelledby="face-l" aria-describedby="face-help" data-test="fallback-face" />
      <Button :label="t('place.button')" severity="secondary" :disabled="s.mesh.state !== 'ready'" data-test="fallback-place" @click="place">
        <template #icon><OuiIcon :icon="target" :size="14" /></template></Button>
    </div>
  </OuiPanel>
</template>

<style>
.em-fallback.em-stage-panel { height: auto; align-self: start; }
.em-fallback > .oui-panel-body { display: grid; gap: var(--oui-s3); }
.em-fallback-row { display: flex; flex-wrap: wrap; align-items: center; gap: var(--oui-s2) var(--oui-s3); }
</style>
