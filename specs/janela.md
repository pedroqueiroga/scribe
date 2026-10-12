# Janela (`scribe/overlay.qml`) *(manual)*

Verificação manual (rodando o app).

- **J1 —** A janela não tem borda e tem fundo translúcido com opacidade ajustável. Solta,
  é uma janela comum, que vai para trás quando outra janela é clicada. Fixa, fica por cima
  das outras janelas (**R10**, em [reader.md](reader.md)).
- **J2 —** Pode ser arrastada pelo fundo e redimensionada pelas bordas, a menos que
  esteja **fixa**.
- **J3 —** Fixa, ela pode também deixar os cliques passarem para o que está embaixo
  ("atravessar"). Nesse modo, a janela inteira deixa os cliques passarem, menos um pequeno
  ícone de cadeado aberto no canto superior direito, que continua visível e clicável e solta
  a janela. O ícone fica na margem direita, fora da área do texto, para nunca cobrir letras. O atalho
  global Ctrl+Alt+F também solta. Nunca existe um estado sem saída pelo mouse.
- **J4 —** A linha da palavra atual fica numa altura fixa da janela (cerca de 40% da
  altura), mesmo em parágrafos maiores que a janela, e a rolagem acompanha a narração com
  animação suave. Rolar com o mouse solta o texto da narração para navegar livremente, e ele
  continua solto até a pessoa pedir. Enquanto está solto, a barra (**J5**) mostra um botão
  só com ícone, uma mira dourada de "recentralizar", sem texto. Clicar nele, ou
  fazer qualquer pulo no áudio (clicar numa palavra, voltar, avançar, atalhos, clicar ou
  arrastar na barra de progresso), volta o texto para a palavra que está sendo narrada.
- **J5 —** Uma barra discreta aparece quando o mouse passa pela janela. Ela mostra o
  capítulo, o progresso, tocar/pausar, a velocidade, fixar, a fonte e a opacidade. A barra
  tem uma faixa própria na base da janela. O texto continua visível ali, esmaecendo por
  baixo da barra, mas a faixa não é clicável para o texto: cliques nela são só da barra
  (ou arrastam a janela), então barra e palavras nunca disputam o mouse. Barra e linha de
  progresso também não disputam: com o mouse sobre a barra, o clique é sempre da barra, e a
  linha de progresso só responde fora dela (isso importa no modo de uma linha, em que as
  duas se encostam). A imagem (**J6**)
  termina acima da faixa.
- **J6 —** As imagens aparecem ao lado do texto, nunca por cima (detalhes em
  [layout.md](layout.md)), com transição suave. Clicar na imagem fecha.
- **J7 —** A fonte é a Roboto embutida no EPUB, quando houver.
- **J8 —** Atalhos globais (exclusivos do scribe, via X11):

  | Atalho              | Ação                        |
  |---------------------|-----------------------------|
  | Ctrl+Alt+P          | tocar / pausar              |
  | Ctrl+Alt+, / .      | voltar / avançar 10 s       |
  | Ctrl+Alt+J / K      | parágrafo anterior / próximo |
  | Ctrl+Alt+[ / ]      | mais devagar / mais rápido  |
  | Ctrl+Alt+H          | mostrar / esconder          |
  | Ctrl+Alt+F          | fixar / soltar              |
- **J9 —** Blocos inteiramente pulados (capa, propaganda, copyright) não aparecem na lista.
  Parágrafos ainda pendentes aparecem normalmente, esmaecidos.
- **J10 —** Enquanto o trecho atual ainda não foi transcrito, um aviso discreto indica
  "carregando o modelo…" ou "transcrevendo…". A barra de progresso mostra também quanto
  do áudio já foi transcrito.
- **J11 —** Fechar o app é silencioso: a posição é salva, a transcrição em andamento para,
  e nenhum erro ou aviso aparece no terminal.
- **J12 —** Pulos seguidos e rápidos (botões ‹‹ ››, atalhos, cliques na barra de progresso
  ou nas palavras) nunca derrubam o app. Verificação: 30 pulos a cada 50 ms, para frente e
  para trás, com o áudio tocando de verdade.
- **J13 —** O texto ocupa toda a largura disponível da janela, qualquer que seja o tamanho
  da fonte. A largura da linha é decidida por quem redimensiona a janela.
- **J14 —** No modo de uma linha ([oneline.md](oneline.md)), aparece só a linha que está
  sendo narrada, centralizada na altura, com o karaokê. A troca de linha desliza. A barra
  aparece ao passar o mouse, encostada à direita por cima do fim da linha, sem o título do
  capítulo, e as palavras à esquerda continuam clicáveis. A altura mínima da janela é a de
  uma linha. Títulos e notas usam o mesmo tamanho do texto (os títulos continuam em
  negrito), para que toda linha caiba exatamente na faixa.
- **J15 —** Um quadradinho na barra mostra o fundo atual (a cor, ou uma miniatura da
  imagem). Clicar nele abre um menu: "Cor do fundo…", "Imagem de fundo…" e, se houver
  imagem, "Remover imagem". A imagem cobre o painel inteiro, cortada nas bordas
  arredondadas, sem distorcer.
- **J16 —** Os seletores de cor e de arquivo só são criados quando a pessoa pede para usá-los.
  Um problema no serviço de diálogos do sistema nunca impede o app de abrir.
- **J17 —** Imagens no modo de uma linha: nada aparece sem a pessoa pedir. Quando a
  narração passa por uma imagem, uma miniatura pequena aparece na ponta direita da faixa,
  com um pulso discreto, e o texto termina antes dela, sem ser coberto. Passar o mouse
  sobre a miniatura abre a imagem grande num balão **fora** da faixa, acima dela se houver
  espaço na tela, ou abaixo. Clicar na miniatura deixa o balão aberto até um novo clique.
  A miniatura mostra a imagem recente (**R14**). Com a barra à mostra, a miniatura fica
  logo à esquerda dela.
