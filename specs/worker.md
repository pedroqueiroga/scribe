# Transcrição em streaming (`scribe/worker.py`)

Testes: [`tests/test_worker.py`](../tests/test_worker.py)

Um processo separado transcreve o áudio em pedaços, sempre começando pelo trecho mais
útil para quem está ouvindo (**T3**, em [store.md](store.md)). As decisões de *quanto* transcrever e *onde cortar*
são funções puras, testáveis sem o Whisper.

- **W1 — Pedaço urgente.** Se o trecho a transcrever começa perto da posição de escuta
  (de 1 s antes até 3 s depois), o pedaço é curto (7 s) para a legenda aparecer rápido.
  Nos outros casos, o pedaço tem 24 s.
- **W2 — Não invadir.** Um pedaço termina antes de um trecho já transcrito que venha
  logo adiante.
- **W3 — Folga.** É transcrito um pouco de áudio além do fim planejado (2 s), para não
  cortar a última palavra. Essa folga não é usada quando o pedaço encosta num trecho já
  transcrito ou no fim do áudio.
- **W4 — Corte nas bordas.** Ficam no pedaço as palavras que terminam até o fim planejado
  (com tolerância de 0,15 s). Se uma palavra atravessa a borda, o pedaço termina no início
  dela, e o próximo pedaço começa ali.
  Mesmo assim, todo pedaço avança pelo menos 0,3 s, para que o worker nunca fique parado
  no mesmo ponto.
- **W5 — Sobras minúsculas.** Um espaço de menos de 0,3 s entre dois trechos transcritos
  é marcado como coberto, sem rodar o Whisper.
- **W6 — Mudança de foco.** Se a posição de escuta muda de um jeito que faz o trecho
  mais útil a transcrever (**T3**) deixar de ser o pedaço em andamento, o worker salva o
  que já reconheceu e passa a transcrever a partir da nova posição. A reprodução normal
  não interrompe nada: a posição avança atrás do pedaço em andamento, e o trecho mais útil
  continua sendo ele. Um pulo para dentro do próprio pedaço (com 2 s de margem antes do
  início) também não interrompe.
- **W7 — Fim.** Quando não há mais nada a transcrever, o worker avisa e termina.
- **W8 — Encerrar.** Um pedido de parada encerra o worker antes de começar o próximo pedaço
  (ou no meio dele), sem salvar nada pela metade.
- **W9 — Órfão.** Se o processo que iniciou o worker deixar de existir sem pedir a parada
  (travou, foi morto à força), o worker se encerra sozinho, como num pedido de parada
  (**W8**): antes do próximo pedaço ou no meio dele, em poucos segundos. Ele nunca continua
  transcrevendo sem ninguém para usar o resultado.
