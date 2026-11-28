// Shapes of the plugin's replies (src/embedder/plugin.py, session.py). Python is the single source of geometry truth.
export type Kind = 'magnet' | 'nfc' | 'nut';
export type Shape = 'disc' | 'block';
export type Mode = 'open' | 'embedded';
export type Polarity = 'N' | 'S';
/** The pocket's outline, picked by the user; without a pick the insert's own (pocket.default_shape). */
export type PocketShape = 'circle' | 'hexagon' | 'square' | 'rectangle';

export interface Preset {
  id: string;
  name: string;
  kind: Kind;
  shape: Shape;
  d?: number;
  l?: number;
  w?: number;
  t: number;
  builtin: boolean;
}

export type MagnetGrade = 'N35' | 'N42' | 'N52' | 'ferrite';
export type FridgeSurface = 'steel' | 'stainless' | 'board';

export interface Settings {
  ui_language: 'auto' | 'en' | 'pt-BR';
  xy_clearance: number;
  z_clearance: number;
  cover_magnet: number;
  cover_nfc: number;
  magnet_grade: MagnetGrade;
  fridge_surface: FridgeSurface;
  user_presets: Preset[];
  pocket_shapes: Record<string, PocketShape>;   // preset id -> the shape picked for it
}
export interface Hello { version: string; settings: Settings }

export interface PartInfo {
  part: number;
  id: string;
  name: string;
  subtype: string;
  embedder: boolean;
  vertices: number;
  triangles: number;
  pos_bytes: number;
  idx_bytes: number;
  pos_chunks: number;
  idx_chunks: number;
}

export interface ObjectInfo {
  object: number;
  id: string;
  name: string;
  item: number;
  instance: number;
  cut: boolean;
  embedded_block: string | null;
  parts: PartInfo[];
}

export interface Project {
  job: string;
  name: string;
  plate: number;
  plates: number;
  config_source: string;
  chunk_bytes: number;
  settings: { layer_height: number | null; first_layer_height: number | null; pause_gcode: boolean; print_sequence: string; raft_layers: number };
  blocks: string[];
  objects: ObjectInfo[];
  existing: { id: string; object_id: string; name: string; label: string; mode: Mode }[];
  pauses: { top_z: number; type: string; extra: string; embedder: boolean }[];
}

export interface Custom { kind: Kind; shape: Shape; d: number; l: number; w: number; t: number }

/** One pocket.plan / project.apply pocket, without the job id. */
export interface PlanArgs {
  object: number;
  part: number;
  tri: number;
  point: [number, number, number];
  preset?: string;
  custom?: Record<string, unknown>;
  mode: Mode;
  spin?: number;
  cover?: number;
  center?: boolean;
  pocket_shape?: PocketShape;
  polarity?: Polarity;
  fridge?: true;              // placed by auto fridge: Python re-checks its hold advisory when it plans or applies
  magnet_grade?: MagnetGrade;   // auto fridge's own grade and surface, when the request named them
  fridge_surface?: FridgeSurface;
}

export interface Plan {
  mode: Mode;
  face?: string;
  shape?: string;           // circle | hexagon | square | rectangle | slot
  size?: number[];          // the fit: what holds the insert
  outer?: number[];         // (x, y) with the corners or vents
  transform?: number[];
  floor?: number | null;
  top?: number | null;
  pause_z?: number | null;
  cover?: number | null;
  label?: string;
  kind?: Kind;
  polarity?: Polarity;
  preview: { positions: number[]; indices: number[] } | null;
  warnings?: string[];
  point?: [number, number, number];   // where it was planned: the face's middle under center
  copies?: number;          // instances of the object on the plate: each gets the insert
  blocked: { code: string; detail: string } | null;
}

export interface Staged { key: number; args: PlanArgs; plan: Plan }

export interface ApplyResult {
  path: string;
  name: string;
  pockets: number;
  removed: number;
  /** `extra` is the comment written into the G-code (English); `items` is the same as data, for the page to word. */
  pauses: { top_z: number; extra: string; items: { label: string; polarity: Polarity | null; n: number }[] }[];
  warnings: string[];
  pruned: number;            // older copies deleted from the plugin folder after this apply
}

export interface CopiesStatus { count: number; bytes: number; kept: number }
export interface CopiesCleared extends CopiesStatus { removed: number; freed: number; failed: number }
