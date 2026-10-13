# Modo completo (`scribe/full.py`)

Testes: [`tests/test_full.py`](../tests/test_full.py)

No modo completo a janela vira um leitor de livros: o livro aparece como o arquivo o
traz (num EPUB, com o HTML e o CSS originais: fontes, recuos, títulos, imagens no lugar),
numa coluna contínua que se rola. O karaokê continua: a palavra narrada ganha um marca-texto, e a página rola
sozinha acompanhando a narração. O comportamento visual está em **J19**–**J22**
([janela.md](janela.md)).

A página é um único documento HTML gerado a partir do arquivo do livro e guardado no
cache do livro (`full/`), com cada palavra marcada com o `id` dela (**E7**, em
[epub.md](epub.md)). A geração é uma função pura dos arquivos; a página só recebe, pela
interface, qual é a palavra atual. Cada formato tem o seu gerador, mas todos cumprem o mesmo
contrato (**C8**, **C9**, **C10**), e o resto do app não sabe de que formato a página veio.

## Formatos

- **C1 — Formatos do livro.** O livro pode ser um EPUB ou um texto puro (`.txt`),
  reconhecido pela extensão (**L1**, em [library.md](library.md)). Numa pasta com um EPUB
  e algum `.txt`, o livro é o EPUB. Os dois passam pelo
  mesmo caminho depois da extração (blocos e palavras, **E1**–**E9**): alinhamento,
  overlay e modo completo. PDF está planejado e ainda não é aceito; pedir um PDF gera uma
  mensagem dizendo isso.
- **C2 — TXT em blocos.** O arquivo é lido como UTF-8 (com ou sem BOM) ou, se não for
  UTF-8 válido, como Latin-1. Uma ou mais linhas em branco separam parágrafos; as quebras
  simples dentro de um parágrafo viram espaço. Um parágrafo de uma linha só, com até 60
  caracteres, com alguma letra ou número e sem terminar em pontuação (`.`, `,`, `;`, `:`,
  `!`, `?`, `…`), aspas ou travessão, é um título (`h`) e começa uma seção nova, com ele de título. O texto antes
  do primeiro título fica numa seção com o nome do arquivo. O título do livro é o nome do
  arquivo. O idioma é `pt` se as palavras mais comuns do português aparecem mais que as do
  inglês, senão `en`; as palavras são normalizadas como no EPUB (**N1**–**N5**).
- **C3 — Página do TXT.** Cada parágrafo aparece com as quebras de linha do arquivo, numa
  fonte de leitura, e os títulos em destaque. Palavras e blocos são marcados como no
  **C8** e no **C9**.

## A página do EPUB

- **C4 — Fidelidade.** Todos os documentos do spine entram na página, na ordem do spine,
  cada um numa seção própria, com o corpo como está no EPUB: as mesmas tags, classes e
  estilos. As folhas de estilo do livro (`<link rel="stylesheet">` e `<style>`) valem para a
  página. Scripts do livro não entram.
- **C5 — Recursos.** Imagens, folhas de estilo e fontes do EPUB são copiadas para o cache,
  e as referências da página (incluindo `url(...)` dentro de `<style>`) apontam para essas
  cópias. Endereços externos e `data:` ficam como estão.
- **C6 — Links internos.** Um link para outro documento do livro vira um link para o mesmo
  ponto dentro da página: para a âncora, se houver, ou para o começo da seção daquele
  documento.
- **C7 — Extração antiga.** Se o texto do `book.json` no cache não bater com o EPUB
  extraído de novo (por exemplo, extraído por uma versão antiga do scribe), as palavras são
  casadas pela sequência de textos. Uma palavra sem par não recebe marca: é melhor ficar sem
  destaque do que destacar a palavra errada.

## Para todo formato

- **C8 — Palavras marcadas.** A página sabe onde está cada palavra do livro: o elemento do
  bloco dela (**C9**) registra o `id` da palavra e o trecho que ela ocupa no texto do bloco
  (início e fim, em caracteres do texto do elemento, como o navegador o conta). O trecho,
  sem a hifenização suave, é o texto da palavra (`t`). Uma palavra que atravessa elementos
  *inline* (a capitular de **E3**) é um trecho só. O que o extrator deixa de fora (chamadas
  de nota, marcas de página, **E4**) continua na página, fora dos trechos das palavras; só
  uma chamada colada no meio de uma palavra (`God!”6).`) fica dentro do trecho dela. A
  página não ganha um elemento por palavra: com um por palavra, um livro de 30 mil palavras
  levava segundos a mais para abrir.
- **C9 — Blocos marcados.** Todo bloco de texto e toda imagem (**E2**) tem na página um
  elemento marcado com o `id` do bloco. Um texto solto num contêiner, que no EPUB não tem
  elemento próprio, ganha um.
- **C10 — Cache.** A página é gerada na primeira vez que o modo completo abre e reaproveitada
  depois. Ela é refeita quando o formato da página muda numa versão nova do scribe.

## O leitor no modo completo

- **C11 — Modo salvo.** O modo completo é uma preferência (**R8**, em
  [reader.md](reader.md)): alternar entre ele e o overlay não interrompe o áudio, e o modo
  em que o app fechou é o modo em que ele abre. `scribe play --full` abre no modo completo
  (e o deixa salvo).
- **C12 — Geometria por modo.** O overlay e o modo completo guardam cada um a sua posição e
  o seu tamanho de janela. Alternar o modo salva a geometria do modo que sai e devolve a do
  modo que entra. Sem geometria salva, o modo completo abre com 900 × 85% da altura da tela,
  centralizado.
- **C13 — Destaque.** A página recebe a palavra atual (**S1**), o bloco atual e se há
  sincronia (**S2**). Na página, a palavra atual tem marca-texto forte, as já ditas do
  bloco atual têm uma marca leve, e o resto fica como no livro. Sem sincronia a marca fica
  esmaecida. Um trecho só do áudio (**A12**) não aparece no modo completo (o texto exibido
  é só o do livro, **P1**); enquanto ele é dito, a marca fica na última palavra do livro.
- **C14 — Clique.** Clicar numa palavra da página faz o mesmo que no overlay (**R1**).
- **C15 — Zoom.** No modo completo, os botões de letra (**J5**) mudam o zoom da página em
  degraus de 10%, entre 50% e 300%, lembrado entre sessões. O tamanho da fonte do overlay
  não muda.
- **C16 — Linha da página.** No modo completo a pessoa escolhe o comprimento da linha do
  texto e onde ela fica na largura da página (**J24**, em [janela.md](janela.md)). O
  comprimento é medido em em, o tamanho da letra da página (acompanha o zoom, **C15**):
  começa em 39 e fica entre 15 e 120, arredondado a décimos. A posição é a fração do espaço
  em branco que fica à esquerda da linha: 0 encosta a linha na margem esquerda, 1 na
  direita e 0,5 centraliza (o padrão), arredondada a milésimos (a centésimos, a ponta que
  fica parada pularia alguns pixels numa tela larga). De cada lado sempre sobra
  uma margem mínima de 2,4 em; numa página estreita demais para o comprimento escolhido, a
  linha ocupa o que cabe. Mover o começo da linha deixa o fim no lugar, mover o fim deixa
  o começo, e mover a linha inteira mantém o comprimento; nenhum deles passa das margens
  mínimas nem dos limites do comprimento. Numa página sem branco sobrando, mover a linha
  inteira não muda nada do que está salvo. Os dois ficam salvos com as preferências
  (**R8**). O overlay não muda: nele o texto ocupa a largura da janela (**J13**).
- **C17 — Maximizada.** No modo completo a janela pode ser maximizada e restaurada (**J25**,
  em [janela.md](janela.md)). Estar maximizada é uma preferência (**R8**): o modo completo
  volta maximizado se estava assim ao sair dele ou ao fechar o app. Enquanto maximizada, a
  geometria salva do modo completo (**C12**) continua a de antes de maximizar, para que
  restaurar devolva o tamanho e o lugar de antes. O overlay nunca abre maximizado: voltar a
  ele de uma janela maximizada devolve a geometria do overlay.

