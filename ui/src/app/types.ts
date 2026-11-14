export interface Settings {
  ui_language: 'auto' | 'en' | 'pt-BR';
  xy_clearance: number;
  z_clearance: number;
  cover_magnet: number;
  cover_nfc: number;
  user_presets: unknown[];
}
export interface Hello { version: string; settings: Settings }
