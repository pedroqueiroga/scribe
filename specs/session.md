# Sessão e linha do tempo (`scribe/session.py`)

Testes: [`tests/test_session.py`](../tests/test_session.py)

- **S1 — Palavra atual.** Para um instante *t*, a palavra atual é a última palavra
  narrada que começa até *t*.
- **S2 — Incerteza.** Se *t* está mais de 4 s depois do fim da última palavra conhecida e
  esse intervalo não foi transcrito, não há palavra atual. A interface mostra que está
  sincronizando.
- **S3 — Atualização ao vivo.** Quando chega um pedaço novo do worker, os tempos são
  recalculados e a versão da linha do tempo aumenta.
- **S4 — Hora da imagem.** Uma imagem aparece quando a narração termina o último texto
  narrado antes dela.
- **S5 — Alinhamento final.** Quando a transcrição termina e houve pedaços novos durante
  a sessão, o alinhamento global é refeito.
- **S6 — Worker morto.** Se o processo de transcrição terminar sem avisar o fim (por
  exemplo, se travar ou for encerrado à força), a sessão passa ao estado de erro, para a
  interface não ficar esperando para sempre.
- **S7 — Momento no texto do áudio.** Para um instante *t* dentro de um trecho só do áudio
  (**A12**), entre o início da primeira palavra e o fim da última, a sessão informa qual é
  o trecho e qual palavra dele está sendo dita. Depois que o trecho termina, e até a
  próxima palavra narrada do livro começar, a última palavra dele continua sendo a
  informada, assim como uma palavra do livro continua atual até a seguinte começar.
