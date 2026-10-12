# Modo de uma linha (`scribe/oneline.py`)

Testes: [`tests/test_oneline.py`](../tests/test_oneline.py)

No modo de uma linha, a janela vira uma faixa estreita que mostra só a linha que está
sendo narrada, como uma legenda. O modo não é um interruptor guardado em algum lugar: ele
é consequência da **altura da janela**. Janela baixa entra no modo de uma linha, e janela
alta sai dele. As contas são funções puras do tamanho da fonte e da altura. O comportamento
visual está em **J14** ([janela.md](janela.md)).

A **altura de uma linha** é medida na tela: é o espaçamento real entre duas linhas do texto
exibido, na fonte e no tamanho atuais (com a Roboto, cerca de 1,7 × o tamanho da fonte).
Uma estimativa não serve: com uma linha medida errado por poucos pixels, a faixa mostra
pedaços de duas linhas ou o vão entre elas. Enquanto a medida não chega, vale a estimativa
de 1,7 × o tamanho da fonte.

- **O1 — Altura de uma linha.** A janela no modo de uma linha tem a altura de uma linha de
  texto, mais 22 px (margens e a linha de progresso), arredondada para cima.
- **O2 — Limite.** O modo normal precisa de espaço para 2,5 linhas de texto mais a faixa da
  barra (48 px). Uma janela mais baixa que isso está no modo de uma linha. Uma janela com
  essa altura ou mais está no modo normal.
- **O3 — Coerência.** Para qualquer altura de linha, a altura do modo de uma linha
  (**O1**) fica abaixo do limite (**O2**). Assim, abrir na altura de uma linha realmente
  entra no modo.
- **O4 — Mudar a fonte.** No modo de uma linha, quando a altura da linha muda (por exemplo,
  ao mudar o tamanho da fonte), a altura da janela se ajusta para caber uma linha da nova
  altura. No modo normal, a altura não muda.
- **O5 — Flag.** `scribe play --oneline` abre a janela na altura de uma linha (**O1**). Sem
  a flag, a janela abre com a altura salva, e o modo segue dela.
- **O6 — Linha inteira.** No modo de uma linha, a faixa mostra sempre uma linha inteira do
  texto, alinhada: nunca pedaços de duas linhas nem o vão entre elas.
