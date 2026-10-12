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
- **R5 — Imagem.** Quando a reprodução passa pela hora de uma imagem (**S4**, em [session.md](session.md)) durante a
  escuta normal, a imagem aparece por 7 s. Quando o ponto é atravessado por um pulo, ela
  não aparece. A imagem pode ser fechada antes do tempo. Os 7 s contam tempo de
  reprodução: com o áudio pausado, a imagem continua à mostra. Qualquer pulo (para frente
  ou para trás, pelo leitor ou pelo tocador) esconde a imagem na hora.
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
  tamanho da janela) são salvas e
  restauradas nas próximas sessões. A fonte fica entre 12 e 64 pontos, a opacidade do fundo
  entre 0 e 1, e a opacidade do texto entre 0,2 e 1 (abaixo disso o texto sumiria; para
  esconder existe o atalho de **J8**). As cores do texto e do fundo são `#rrggbb`, e um
  valor inválido é ignorado, mantendo a cor anterior. A cor e a opacidade do texto valem para todo o texto
  exibido: o karaokê (**R6**) aplica as suas transparências por cima da opacidade escolhida.
- **R9 — Posição inicial.** O leitor começa na posição salva do livro (**L6**, em
  [library.md](library.md)) e salva a posição atual ao fechar.
- **R10 — Modo da janela.** O leitor decide o comportamento da janela a partir das
  preferências: fixa significa também ficar por cima das outras janelas, e os cliques só
  atravessam a janela quando ela está fixa e essa opção está ligada. Soltar a janela
  desliga o atravessar cliques, porque senão ela não poderia mais ser clicada (**J3**,
  em [janela.md](janela.md)).
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
  janela acompanha a linha. O trecho só aparece depois que a narração chega nele.
- **R14 — Imagem recente.** O leitor informa a imagem mais recente pela qual a narração já
  passou no capítulo atual (pela hora de **S4**). O capítulo de uma imagem é o do texto
  narrado logo antes dela: uma seção do EPUB que só tem uma ilustração pertence ao capítulo
  anterior. Ela continua sendo a imagem recente até a
  narração passar pela próxima imagem ou sair do capítulo. Voltar no áudio para antes dela
  faz a recente voltar a ser a anterior (ou nenhuma). É ela que a miniatura do modo de uma
  linha mostra (**J17**).
