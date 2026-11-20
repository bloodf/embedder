<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import Button from 'primevue/button';
import { OuiIcon, OuiPanel } from '@orca-plugins/ui-foundation/src/components';
import { box, target } from '@orca-plugins/ui-foundation/src/icons';
import { s } from '../app/store';
import { currentObject, dragEnd, dragStart, meshesOf, moveTo, placeAt, removeInHand, selectStaged } from '../app/project';
import { hitOf, previewsFor, sizeOf, turn } from '../app/logic';
import { createScene, type InHand, type SceneApi } from '../core/scene';
import type { Hit } from '../core/pick';
import { theme } from '../core/theme';
import { t, fmt } from '../core/i18n';

const STEP_MM = 0.5, BIG_STEP_MM = 5, TURN_DEG = 15;
const ARROWS: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] };

// three.js objects stay in this plain variable, never in Vue state.
let scene: SceneApi | null = null;
// The shape drawn for the pocket in hand: its last plan that had one. A plan that is blocked has none, so the pocket
// keeps the shape it had, in red, at the spot that blocks it.
let drawn: Omit<InHand, 'tone'> | null = null;
let drawnFor: number | null = null;   // the pocket of the list it is the shape of; null: a new pocket
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
  if (!s.hit || s.selected !== drawnFor) drawn = null;   // another pocket in hand never wears this one's shape
  drawnFor = s.selected;
  if (s.hit && s.plan?.preview && s.planArgs) drawn = { preview: s.plan.preview, base: hitOf(s.planArgs) };
  const tone = s.plan?.blocked ? 'blocked' : s.plan?.warnings?.length ? 'warn' : 'ok';
  scene?.setPockets(drawn && { ...drawn, tone }, previewsFor(s.staged, s.object, s.selected));
  scene?.pose(s.hit);
}

/** Where the pocket in hand is: the face's middle Python moved it to, while it is centred there; else where it was put. */
function inHandAt(hit: Hit): Hit {
  return s.center && s.planArgs?.center && s.plan?.point ? { ...hit, point: s.plan.point } : hit;
}

/** With a pocket in hand: arrows step it along its face, R turns it, Delete removes it, Escape lets go of it. */
function onKey(e: KeyboardEvent) {
  if (e.altKey || e.ctrlKey || e.metaKey) return;
  const arrow = ARROWS[e.key];
  if (e.key === 'Escape') {
    if (!scene?.cancel()) {   // a drag is called off and the pocket stays in hand; otherwise the pocket is let go
      if (s.selected == null) return;
      selectStaged(null);
    }
  } else if (!s.hit || s.dragging) {
    return;
  } else if (arrow) {
    moveTo(scene?.nudge(inHandAt(s.hit), arrow[0], arrow[1], e.shiftKey ? BIG_STEP_MM : STEP_MM) ?? null);
  } else if (e.key === 'r' || e.key === 'R') {
    s.spin = turn(s.spin, e.shiftKey ? -TURN_DEG : TURN_DEG);
  } else if (e.key === 'Delete' || e.key === 'Backspace') {
    removeInHand();
  } else {
    return;
  }
  e.preventDefault();
}

onMounted(() => {
  if (!host.value) return;
  try {
    scene = createScene(host.value, { pick: (hit, onHand) => { if (!onHand || s.selected == null) void placeAt(hit); }, select: selectStaged, dragStart, dragMove: moveTo, dragEnd });
  } catch {
    s.webgl = false;   // the probe passed but this context did not: fall back to the numeric form
    return;
  }
  showParts();
  showPockets();
});
watch(() => [s.mesh.version, s.object], () => { showParts(); showPockets(); });
watch(() => [s.plan, s.staged, s.selected], showPockets);
// A move only slides what is drawn; the meshes are built again when Python answers with the pocket planned there.
watch(() => s.hit, hit => { if (hit) scene?.pose(hit); else showPockets(); });
// The scene reads its colours from the palette when it builds its materials: build them again in the new theme.
watch(theme, () => { showParts(false); showPockets(); });

// In one column the form sits above the view, and its plan block grows and shrinks as the pocket in hand is planned.
// While the user works in the view (it has the focus), the view stays where it is on the screen: a pocket must not
// slip from under the pointer because the page above it changed height. `stageTop` is where the view was when the
// user last pressed a button or a key in it, or scrolled the page; `stageAt` is where it was in the page then. A
// scroll that leaves the view where it was in the page is the user's (or the correction's own) and stands; one that
// comes with the page above changing height (the browser keeping the scroll in range) is left to the correction.
let stageTop = 0, stageAt = 0;
const keepTop = () => {
  stageTop = host.value?.getBoundingClientRect().top ?? 0;
  stageAt = stageTop + window.scrollY;
};
const scrolled = () => {
  if (host.value && Math.abs(host.value.getBoundingClientRect().top + window.scrollY - stageAt) < 0.5) keepTop();
};
const pageGrew = new ResizeObserver(() => {
  if (!host.value || document.activeElement !== host.value) return;
  const top = host.value.getBoundingClientRect().top, shift = top - stageTop;
  stageAt = top + window.scrollY;   // the page moved the view; scrolling does not change this
  if (Math.abs(shift) >= 0.5) window.scrollBy(0, shift);
});
onMounted(() => {
  for (const type of ['focus', 'pointerdown', 'keydown']) host.value?.addEventListener(type, keepTop, true);
  window.addEventListener('scroll', scrolled, { passive: true });
  pageGrew.observe(document.body);
});
onBeforeUnmount(() => {
  window.removeEventListener('scroll', scrolled);
  pageGrew.disconnect();
  scene?.dispose();
  scene = null;
});
</script>

<template>
  <OuiPanel class="em-viewer" :title="object?.name ?? t('view.label')" :icon="box" tone="sky" flush data-test="viewer" :aria-label="t('view.label')">
    <template #meta>{{ s.mesh.state === 'loading' ? t('view.loading', { done: s.mesh.done, total: s.mesh.total }) : size }}</template>
    <template #actions>
      <Button :label="t('view.fit')" severity="secondary" text size="small" @click="scene?.fit()"><template #icon><OuiIcon :icon="target" :size="14" /></template></Button>
    </template>
    <div class="em-stage">
      <div ref="host" class="em-stage-host" tabindex="0" role="application" :aria-label="t('view.label')" aria-describedby="em-view-keys" data-test="stage" @keydown="onKey" />
      <p id="em-view-keys" class="oui-sr">{{ t('view.keys') }}</p>
      <p class="oui-meta em-hint">{{ t('view.hint') }}</p>
    </div>
  </OuiPanel>
</template>

<style>
/* The view takes the height its grid cell gives the panel: the canvas is out of flow, so it can never set that height. */
.em-viewer > .oui-panel-body { display: grid; min-height: 0; }
.em-stage { position: relative; min-height: 0; overflow: hidden; background: var(--oui-inset); border-radius: 0 0 var(--oui-radius-lg) var(--oui-radius-lg); }
.em-stage-host { position: absolute; inset: 0; cursor: crosshair; touch-action: none; }
.em-stage-host[data-over] { cursor: grab; }
.em-stage-host[data-drag] { cursor: grabbing; }
/* foundation-gap: the foundation's focus ring sits 2 px outside its element; the stage clips there, so this one is drawn inside. */
.orca-ui .em-stage-host:focus-visible { outline-offset: -2px; }
.em-stage-host > canvas { position: absolute; inset: 0; display: block; }
.em-hint { position: absolute; inset: auto var(--oui-s3) var(--oui-s3); text-align: center; pointer-events: none; }
</style>
