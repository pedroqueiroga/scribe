# Alinhamento (`scribe/align.py`)

Testes: [`tests/test_align.py`](../tests/test_align.py)

O alinhamento casa os tokens do livro com os tokens da transcrição. Cada palavra do livro
termina num de três estados:

- **narrada**, com início e fim no áudio;
- **pulada**, quando não foi lida no audiobook (capa, copyright, propaganda, legendas);
- **pendente**, quando ainda não dá para saber, porque falta transcrição daquele trecho.

Requisitos:

- **A1 — Casamento exato.** Quando a transcrição é igual ao texto do livro, toda palavra
  fica narrada com o tempo da palavra transcrita correspondente.
- **A2 — Tolerância a erros.** Erros de reconhecimento ("Casey" por "KC", palavras com
  letras trocadas) não impedem o alinhamento do resto do trecho. As palavras não
  reconhecidas ganham tempo por interpolação (**A5**).
- **A3 — Texto não lido.** Um trecho do livro entre dois pontos casados, com mais de 3
  palavras, é **pulado** se o narrador disse menos de 35% dessa quantidade de palavras no
  mesmo intervalo de tempo. Texto antes do primeiro ponto casado (ou depois do último),
  com mais de 8 palavras, também é pulado quando aquele trecho do áudio já foi transcrito.
- **A4 — Casamentos por acaso.** Palavras casadas soltas, que não formam um grupo de pelo
  menos 3 tokens próximos no livro (até 3 posições de distância) e no tempo (até 3 s),
  são descartadas.
- **A5 — Interpolação.** Palavras narradas sem par recebem tempos entre os pontos casados
  vizinhos, proporcionais ao número de letras de cada uma.
- **A6 — Ordem.** Os tempos das palavras narradas nunca diminuem ao longo do livro.
- **A7 — Pendência.** Se o intervalo entre dois pontos casados não está totalmente
  transcrito, as palavras entre eles ficam pendentes (**P4**, em [SPEC.md](../SPEC.md)).
- **A8 — Pedaço novo (incremental).** Um pedaço de transcrição avulso é localizado no
  livro (por votação de trigramas) e alinhado só naquela região. O resultado deve ser
  equivalente ao do alinhamento global para o mesmo trecho.
- **A9 — Pedaço sem correspondência.** Um pedaço só é aceito se pelo menos metade dos seus
  tokens casa com o livro, ou se ele contém uma sequência de pelo menos 8 tokens seguidos
  casados (pedaço que é parte livro, parte vinheta). Fora isso (vinheta, créditos, outro
  livro, coincidência de umas poucas palavras), o pedaço é ignorado e não altera nenhum tempo.
- **A10 — Refazer um trecho.** Um pedaço novo substitui os casamentos anteriores que
  caíam no mesmo intervalo de tempo.
- **A11 — Narrador fora do livro.** Quando o narrador fala muito mais do que o texto
  entre dois pontos casados (mais que o triplo do tempo esperado, mais 2 s), as palavras
  do livro não são esticadas sobre todo o intervalo.
- **A12 — Texto só do áudio.** Um trecho da transcrição vira "texto só do áudio" quando
  todas as condições abaixo valem:
  1. São palavras transcritas seguidas cujo tempo não coincide com o de nenhuma palavra
     narrada do livro.
  2. O trecho fica entre duas palavras narradas do livro. Créditos antes da primeira e
     material depois da última ficam de fora.
  3. Entre essas duas palavras nada está pendente: o áudio do intervalo foi todo transcrito
     e o livro não tem palavras pendentes ali (**A7**).
  4. A confiança é alta: toda palavra do trecho tem probabilidade de pelo menos 0,5, e a
     média do trecho é de pelo menos 0,7. (Uma palavra isolada dita com ênfase, como o
     "Lazy." lido de uma imagem, costuma vir com uma confiança um pouco menor; as condições
     5 e 6 cuidam do ruído.)
  5. O trecho cai numa quebra do livro: entre as duas palavras há uma imagem, ou elas estão
     em parágrafos diferentes. Palavras que o narrador acrescenta no meio de uma frase ("of
     *your* decisions") ficam de fora.
  6. O trecho não está no livro em outro lugar próximo. Se ele tem 3 palavras ou mais, e a
     maioria das suas sequências de 3 palavras aparece no livro a até 2000 palavras de
     distância, ele é texto do livro lido fora de ordem (por exemplo, uma nota de rodapé
     lida no meio do parágrafo) e fica de fora.

  Cada trecho guarda as palavras com o texto da transcrição (com a pontuação dela) e os
  tempos, e fica associado à última palavra narrada do livro antes dele.
