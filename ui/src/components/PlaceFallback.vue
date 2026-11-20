<script setup lang="ts">
import { ref } from 'vue';
import Button from 'primevue/button';
import Select from 'primevue/select';
import { OuiEmpty, OuiIcon, OuiPanel } from '@orca-plugins/ui-foundation/src/components';
import { box, eye, target } from '@orca-plugins/ui-foundation/src/icons';
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
  <OuiPanel class="em-fallback" :title="t('no3d.title')" :icon="box" tone="sky" flush data-test="no3d">
    <OuiEmpty :icon="eye" tone="sky" :title="t('embed.no3d')" :text="t('no3d.help')">
      <template #actions>
        <label id="face-l" class="oui-meta oui-strong">{{ t('place.face') }}</label>
        <Select v-model="face" :options="faces.map(f => ({ value: f.value, label: t(f.label) }))" option-label="label" option-value="value"
                aria-labelledby="face-l" data-test="fallback-face" />
        <Button :label="t('place.button')" severity="secondary" :disabled="s.mesh.state !== 'ready'" data-test="fallback-place" @click="place">
          <template #icon><OuiIcon :icon="target" :size="14" /></template></Button>
      </template>
    </OuiEmpty>
  </OuiPanel>
</template>

<style>
.em-fallback .oui-empty .oui-row { justify-content: center; }
</style>
