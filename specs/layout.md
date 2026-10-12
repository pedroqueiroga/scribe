# Imagem ao lado do texto (`scribe/layout.py`)

Testes: [`tests/test_layout.py`](../tests/test_layout.py)

Quando uma ilustração está à mostra (**R5**, em [reader.md](reader.md)), a imagem
aparece **ao lado** do texto, nunca por cima dele. O ideal é a janela abrir espaço para a
imagem crescendo para a direita, sem mexer na largura do texto. As decisões de tamanho são
uma função pura, que recebe a geometria da janela e da tela.

- **G1 — Painel da imagem.** A imagem ocupa um painel à direita do texto, com a altura útil
  da janela e largura proporcional à imagem, sem distorcer. O painel nunca é mais largo que
  a largura atual do texto.
- **G2 — Crescer para a direita.** Se a tela tem espaço à direita da janela, a janela cresce
  exatamente a largura do painel (mais o espaçamento entre texto e imagem), e o texto
  mantém a sua largura.
- **G3 — Pouco espaço.** Se a tela não tem espaço suficiente à direita, a janela cresce até
  a borda da tela, e o texto cede só o que faltar. O texto nunca fica mais estreito que
  280 px. Se mesmo assim não couber, o painel encolhe (e a imagem junto, sem distorcer).
- **G4 — Voltar ao normal.** Quando a imagem some, a janela perde exatamente o que cresceu,
  e o texto volta à largura de antes.
- **G5 — Crescimento temporário.** Enquanto a janela está crescida por causa de uma imagem,
  a geometria salva nas preferências (**R8**) é a de antes do crescimento.
- **G6 — Troca de imagem.** Se outra imagem aparece enquanto uma já está à mostra, o espaço
  é recalculado a partir do tamanho original da janela, sem acumular crescimentos.

## Modo vertical

Uma janela estreita e alta, encostada na lateral da tela, não tem para onde crescer sem
roubar espaço do que está ao lado. Nela a imagem entra **no próprio texto**, no lugar em que
está no livro, como numa página. Como o modo de uma linha (**O2**, em
[oneline.md](oneline.md)), o modo vertical não é um interruptor: é consequência do formato
da janela. O comportamento visual está em **J18** ([janela.md](janela.md)).

- **G7 — Formato.** Uma janela mais alta que larga está no modo vertical, a menos que esteja
  no modo de uma linha. Perto do quadrado há uma folga, para o modo não ficar trocando a
  cada pixel: a janela só entra no modo vertical quando a altura passa de 1,15 × a largura,
  e só sai quando a altura fica menor que a largura. Entre os dois, continua no modo em que
  está. Com o painel da imagem aberto, vale a largura de antes do crescimento (**G5**).
  No modo vertical o painel ao lado (**G1**) nunca abre, e a janela
  não cresce por causa de imagens.
- **G8 — Imagens no texto.** No modo vertical, cada imagem que tem hora (**S4**, em
  [session.md](session.md)) aparece no texto, entre os parágrafos, no lugar dela no livro, o
  tempo todo, e não só na janela de tempo (**R5**). Imagens sem hora (a capa, por exemplo,
  que não tem texto narrado antes dela) não aparecem.
- **G9 — Tamanho no texto.** A imagem no texto ocupa a largura do texto, sem distorcer, mas
  nunca passa de 60% da altura da janela (para a linha atual, em **J4**, não sair de vista)
  nem do tamanho original da imagem.
- **G10 — Foco na imagem.** De 1 s antes da hora de uma imagem (a mesma antecedência do
  **R5**) até começar a primeira palavra narrada depois dela, a imagem é o **foco**. No modo
  vertical, enquanto isso a rolagem centraliza a imagem na janela, em vez de manter a linha
  da palavra atual a 40% da altura (**J4**). Quando a palavra seguinte começa, o foco volta
  ao texto. Se nenhuma palavra narrada vem depois, o foco dura o tempo do **R5**. O foco
  depende só da posição, como no **R5**: um pulo para dentro do intervalo também o dá.
