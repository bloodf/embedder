// Every visible string of the Embedder page, in English and Brazilian Portuguese. Texts that come from Python
// (error details) are shown inside these, not translated.
export const en = {
  'app.title': 'Embedder',
  'app.brand': 'Embedder',
  'nav.label': 'Embedder sections',
  'nav.embed': 'Embed',
  'nav.settings': 'Settings',

  'embed.empty.title': 'No project loaded',
  'embed.empty.body': 'Load the current project to place magnets and NFC tags. Your original project is never changed.',
  'embed.no3d': 'The 3D view is not available in this window.',
  'settings.empty.title': 'Settings',
  'settings.empty.body': 'Clearances and cover thickness will be set here.',

  'common.ok': 'OK',
  'common.close': 'Close',
  'common.goBack': 'Go back',
  'common.dismiss': 'Dismiss',

  'msg.region': 'Messages',
  'msg.waiting': '{action}: waiting for the plugin…',
  'msg.failed': '{action} failed: {error}',
  'msg.unknown': '{action}: no answer after {seconds} s. It may still finish.',
  'msg.lateOk': '{action} finished after all.',
  'msg.lateError': '{action} failed after all: {error}',
  'msg.plugin': 'Plugin error: {error}',
} as const;

export type MessageKey = keyof typeof en;

export const ptBR: Record<MessageKey, string> = {
  'app.title': 'Embedder',
  'app.brand': 'Embedder',
  'nav.label': 'Seções do Embedder',
  'nav.embed': 'Embutir',
  'nav.settings': 'Configurações',

  'embed.empty.title': 'Nenhum projeto carregado',
  'embed.empty.body': 'Carregue o projeto atual para posicionar ímãs e etiquetas NFC. O projeto original nunca é alterado.',
  'embed.no3d': 'A visualização 3D não está disponível nesta janela.',
  'settings.empty.title': 'Configurações',
  'settings.empty.body': 'Folgas e espessura da cobertura serão ajustadas aqui.',

  'common.ok': 'OK',
  'common.close': 'Fechar',
  'common.goBack': 'Voltar',
  'common.dismiss': 'Dispensar',

  'msg.region': 'Mensagens',
  'msg.waiting': '{action}: aguardando o plugin…',
  'msg.failed': '{action} falhou: {error}',
  'msg.unknown': '{action}: sem resposta após {seconds} s. Pode ainda terminar.',
  'msg.lateOk': '{action} terminou, afinal.',
  'msg.lateError': '{action} falhou, afinal: {error}',
  'msg.plugin': 'Erro do plugin: {error}',
};
