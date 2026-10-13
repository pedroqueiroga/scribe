# Leitor (`scribe/reader.py`)

Testes: [`tests/test_reader.py`](../tests/test_reader.py)

O leitor é a parte que conecta o tocador de áudio, a sessão e a interface. Ele é testado
com um tocador falso.

- **R1 — Clique numa palavra.** Clicar numa palavra narrada leva o áudio para o início
  dela. Clicar numa palavra sem tempo leva à próxima palavra narrada.
- **R2 — Parágrafos.** "Parágrafo anterior" volta ao início do parágrafo atual se já se
  passaram mais de 2 s dele; senão, vai ao anterior. "Próximo parágrafo" vai ao início
  do próximo parágrafo narrado.
- **R3 — Pulos de tempo** (±10 s) ficam dentro dos limites do áudio.
- **R4 — Velocidade** anda em degraus fixos (0,75× a 2×), sem passar dos extremos, e é
  lembrada por livro.
- **R5 — Imagem à mostra.** A imagem fica à mostra numa janela de tempo em volta da hora
  dela (**S4**, em [session.md](session.md)): entra 1 s antes, para encaixar com o fim da
  leitura do texto que a precede, e sai 10 s depois. Vale o mesmo nos dois modos da janela
  (ao lado do texto, **J6**; miniatura, **J17**). A regra depende só da posição de escuta:
  com o áudio pausado a imagem continua como está, e depois de um pulo vale a posição nova
  (cair dentro da janela de uma imagem a mostra; cair fora a esconde). Quando a janela da
  próxima imagem começa, ela substitui a anterior. A imagem também sai quando a narração
  deixa o capítulo dela (**R14**).
- **R6 — Karaokê.** No parágrafo atual, as palavras já ditas e a palavra atual aparecem
  com destaque total, e as seguintes aparecem esmaecidas. Os outros parágrafos ficam todos
  esmaecidos. Palavras puladas ficam ainda mais apagadas. No texto exibido, cada palavra
  é um link próprio (para o clique de **R1**), e caracteres especiais do livro aparecem
  como texto, sem virar marcação.
  O leitor também informa onde a palavra atual começa no texto do parágrafo (em
  caracteres), para a janela manter a linha atual à vista (**J4**, em [janela.md](janela.md)).
- **R7 — Avisar o worker.** A posição de escuta é enviada ao worker a cada 5 s e
  imediatamente após um pulo.
- **R8 — Preferências** (tamanho da fonte, cor do fundo, imagem de fundo, opacidade do
  fundo, cor do texto, opacidade do texto, janela fixa, cliques atravessando, posição e
  tamanho da janela, altura do foco (**R15**), modo completo, zoom e linha da página, janela maximizada, **C11**–**C17** em
  [completo.md](completo.md)) são salvas e
  restauradas nas próximas sessões. A fonte fica entre 12 e 64 pontos, a opacidade do fundo
  entre 0 e 1, e a opacidade do texto entre 0,2 e 1 (abaixo disso o texto sumiria; para
  esconder existe o atalho de **J8**). As cores do texto e do fundo são `#rrggbb`, e um
  valor inválido é ignorado, mantendo a cor anterior. A cor e a opacidade do texto valem para todo o texto
  exibido: o karaokê (**R6**) aplica as suas transparências por cima da opacidade escolhida.
- **R9 — Posição inicial.** O leitor começa na posição salva do livro (**L6**, em
  [library.md](library.md)) e salva a posição atual ao fechar.
- **R10 — Modo da janela.** O leitor decide o comportamento da janela a partir das
  preferências: fixa significa também ficar por cima das outras janelas, e os cliques só
  atravessam a janela quando ela está fixa e essa opção está ligada. Ligar o atravessar
  com a janela solta também a fixa. O cadeado (**J3**, em [janela.md](janela.md)), com os
  cliques atravessando, desfaz só o que o atravessar fez: se a janela já estava fixa antes,
  ela continua fixa e só o atravessar desliga; se foi o atravessar que a fixou, ela também
  é solta. Sem atravessar, o cadeado fixa ou solta a janela, e soltá-la sempre desliga o
  atravessar, porque senão ela não poderia mais ser clicada. Tudo isso fica salvo entre
  sessões.
- **R11 — Fechar pausa na hora.** Fechar o app (pelo botão, pelo gerenciador de janelas ou
  pelo atalho) pausa o áudio antes de qualquer outra coisa. O resto do encerramento (salvar
  a posição, parar a transcrição) acontece depois, com o áudio já em silêncio.
- **R12 — Imagem de fundo.** O fundo pode ser uma cor (**R8**) ou uma imagem escolhida pela
  pessoa. A imagem é copiada para a pasta de dados do scribe (`backgrounds/`), e a
  preferência guarda a cópia. Assim o fundo continua funcionando mesmo se o arquivo
  original for movido ou apagado. Um arquivo que não existe ou que não é imagem é ignorado,
  e o fundo anterior continua. Remover a imagem volta para a cor de fundo. A opacidade do
  fundo vale para a cor e para a imagem.
- **R13 — Exibir o texto do áudio.** Um trecho só do áudio (**A12**) aparece no fim do
  parágrafo da palavra do livro a que ele está associado, numa linha própria, em itálico,
  marcado como vindo do áudio. O karaokê vale também para ele: enquanto o trecho está
  sendo dito, o parágrafo dele é o atual, as palavras já ditas ficam destacadas, e a
  janela acompanha a linha. Quando o trecho termina, a janela fica na linha dele até a
  próxima palavra do livro: não volta para a palavra do livro dita antes do trecho.
  O trecho só aparece depois que a narração chega nele.
- **R14 — Capítulo da imagem.** O capítulo de uma imagem é o do texto narrado logo antes
  dela: uma seção do EPUB que só tem uma ilustração pertence ao capítulo anterior. Uma
  imagem só fica à mostra (**R5**) enquanto a palavra atual está no capítulo dela.
- **R15 — Altura do foco.** A linha da palavra atual fica a uma altura escolhida pela
  pessoa, dada como fração da altura da área do texto, de cima para baixo: perto de 0 mostra
  mais texto ainda por ler, perto de 1 mostra mais texto já lido, e 0,5 é o meio. Começa em
  0,4 e fica entre 0,2 e 0,75, para a linha nunca cair na borda esmaecida (**J4**), sempre
  arredondada a centésimos. É uma só para o overlay, o modo vertical e o modo completo
  (**J4**, **J20**). O modo de uma linha a ignora, porque nele só há a linha atual (**J14**).
  Fica salva com as outras preferências (**R8**). Uma imagem em foco (**G10**) continua
  centralizada, para aparecer inteira.
