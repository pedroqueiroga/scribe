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
