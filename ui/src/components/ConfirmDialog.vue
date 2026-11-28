<script setup lang="ts">
import Dialog from 'primevue/dialog';
import Button from 'primevue/button';
import InputText from 'primevue/inputtext';
import { OuiConfirm } from '@orca-plugins/ui-foundation/src/components';
import { dialog, close, restoreFocus } from '../core/dialog';
import { t } from '../core/i18n';

function onVisible(v: boolean) { if (!v) close(dialog.cancelValue); }
const closeButton = () => ({ severity: 'secondary', text: true, rounded: true, 'aria-label': t('common.close') });
</script>
<template>
  <!-- A question with one field (the name of a preset) is a plain dialog; every other protected decision is the shared confirmation. -->
  <Dialog v-if="dialog.input" :visible="dialog.visible" modal :header="dialog.title" :draggable="false" :style="{ width: '420px', maxWidth: 'calc(100vw - 32px)' }"
          :close-button-props="closeButton()" data-dlg @update:visible="onVisible" @after-hide="restoreFocus">
    <form id="em-dlg-form" class="oui-confirm-body" @submit.prevent="close(dialog.inputValue)">
      <p class="em-dlg-text">{{ dialog.text }}</p>
      <div class="oui-field">
        <label for="dlg-input">{{ dialog.input.label }}</label>
        <InputText id="dlg-input" v-model="dialog.inputValue" :placeholder="dialog.input.placeholder" autofocus fluid />
      </div>
    </form>
    <template #footer>
      <Button :label="dialog.no ?? t('common.cancel')" severity="secondary" data-dlg="cancel" @click="close(dialog.cancelValue)" />
      <Button :label="dialog.yes ?? t('common.ok')" type="submit" form="em-dlg-form" data-dlg="confirm" :disabled="!dialog.inputValue.trim()" />
    </template>
  </Dialog>
  <OuiConfirm v-else :visible="dialog.visible" :title="dialog.title" :confirm-label="dialog.yes ?? t('common.ok')" :cancel-label="dialog.no ?? t('common.cancel')"
              :danger="dialog.danger" :draggable="false" :close-button-props="closeButton()" @update:visible="onVisible" @confirm="close(true)" @after-hide="restoreFocus">
    <p class="em-dlg-text">{{ dialog.text }}</p>
  </OuiConfirm>
</template>
<style>
.em-dlg-text { white-space: pre-line; }
</style>
