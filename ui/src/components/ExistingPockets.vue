<script setup lang="ts">
import Button from 'primevue/button';
import { OuiHint, OuiIcon } from '@orca-plugins/ui-foundation/src/components';
import { trash } from '@orca-plugins/ui-foundation/src/icons';
import { s } from '../app/store';
import { markRemove } from '../app/project';
import { t, insertLabel } from '../core/i18n';
</script>

<!-- The pockets an earlier Apply left in the project, as rows like the staged ones. The bin marks one for removal in
     the new copy: its row is struck through and says so, with Undo in the bin's place. -->
<template>
  <div class="em-existing">
    <div class="em-labelled em-existing-head"><p id="em-existing-l" class="oui-label">{{ t('list.existing') }}</p><OuiHint :label="t('list.existing')">{{ t('list.existingHelp') }}</OuiHint></div>
    <ul class="em-rows" aria-labelledby="em-existing-l" data-test="existing">
      <li v-for="x in s.project?.existing ?? []" :key="x.id" :data-removed="s.remove.includes(x.id) || undefined">
        <span class="em-row-id">
          <span class="oui-strong em-existing-name">{{ insertLabel(x.label) }}</span>
          <span class="oui-meta" role="status">{{ s.remove.includes(x.id) ? t('list.willRemove') : t(`mode.${x.mode}`) }}</span>
        </span>
        <!-- One button that changes its face, so the focus stays on it through a press. -->
        <Button :id="'rm-' + x.id" text size="small" :severity="s.remove.includes(x.id) ? 'secondary' : 'danger'" :label="s.remove.includes(x.id) ? t('list.undo') : undefined"
                :aria-label="s.remove.includes(x.id) ? t('list.keepExisting', { label: insertLabel(x.label) }) : t('list.removeExisting', { label: insertLabel(x.label), mode: t(`mode.${x.mode}`) })"
                @click="markRemove(x.id, !s.remove.includes(x.id))">
          <template v-if="!s.remove.includes(x.id)" #icon><OuiIcon :icon="trash" :size="14" /></template></Button>
      </li>
    </ul>
  </div>
</template>

<style>
.em-existing-head { padding: var(--oui-s3) var(--oui-s4) var(--oui-s1); }
.em-existing .em-rows > li { min-height: 44px; }
.em-existing .em-rows > li[data-removed] .em-existing-name { text-decoration: line-through; color: var(--oui-muted); }
.em-list .oui-panel-body > * + .em-existing { border-top: 1px solid var(--oui-border); }
</style>
