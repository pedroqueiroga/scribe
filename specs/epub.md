# Extração do EPUB (`scribe/epub.py`)

Testes: [`tests/test_epub.py`](../tests/test_epub.py)

O livro é lido na ordem de leitura do EPUB (o *spine*) e vira uma lista de **seções**.
Cada seção tem **blocos**, e cada bloco de texto tem **palavras**.

- **E1 — Ordem.** As seções seguem a ordem do spine, e os blocos seguem a ordem em que
  aparecem no documento.
- **E2 — Tipos de bloco.** Títulos (`h1`–`h6`) viram blocos `h`, itens de lista viram `li`,
  parágrafos e demais textos viram `p`, notas de rodapé viram `note` e imagens viram `img`.
- **E3 — Palavras inteiras.** O texto de um bloco é montado sem inserir espaços entre
  elementos *inline*. Uma capitular (`<span>w</span>hen`) resulta em "when", não "w hen".
- **E4 — Sem chamadas de nota nem marcas de página.** Números de chamada de nota de rodapé
  e marcadores de quebra de página não aparecem no texto do parágrafo.
- **E5 — Notas de rodapé** (listas ou elementos marcados como footnote/endnote) viram
  blocos do tipo `note`, na posição em que aparecem.
- **E6 — Imagens.** Imagens de conteúdo viram blocos `img`, e o arquivo é copiado para o
  cache. Imagens decorativas (`role="presentation"`, ícones inline) são ignoradas.
- **E7 — Identificadores.** Todo bloco e toda palavra recebem um `id` numérico global,
  crescente na ordem de leitura e começando em 0.
- **E8 — Idioma** vem de `dc:language`. Variantes de português viram `pt`, e o resto
  vira `en`.
- **E9 — Título da seção** vem do sumário do EPUB. Se a seção não estiver no sumário,
  usa o `<title>` do documento.

### Normalização (para o alinhamento)

Cada palavra guarda o texto original (`t`) e uma lista de tokens normalizados (`n`).
A normalização existe para que o texto do livro e a transcrição possam ser comparados.

- **N1 —** Minúsculas, sem acentos, sem pontuação. Apóstrofos são removidos: "it’s" vira `its`.
- **N2 —** Números viram palavras no idioma do livro: "5" vira `five` em inglês e `cinco`
  em português. Ordinais e anos também são convertidos ("1990" vira `nineteen ninety`).
- **N3 —** Travessões, barras e reticências separam palavras: "done—all" vira `done`, `all`.
- **N4 —** "&" vira `and` (ou `e`), e "%" vira `percent` (ou `por cento`).
- **N5 —** Um token que só tem pontuação gera lista vazia.
