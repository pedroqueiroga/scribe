# Armazenamento da transcrição (`scribe/store.py`)

Testes: [`tests/test_store.py`](../tests/test_store.py)

A transcrição é guardada em **pedaços**. Cada pedaço tem início `s`, fim `e` (em segundos
do áudio) e as palavras reconhecidas, cada uma com seu tempo.

- **T1 — Persistência.** Cada pedaço adicionado é gravado como um arquivo próprio,
  de forma atômica. Um novo armazenamento aberto na mesma pasta enxerga os mesmos pedaços.
- **T2 — Cobertura.** O armazenamento sabe quais intervalos do áudio já foram transcritos.
  Pedaços encostados ou sobrepostos formam um único intervalo.
- **T3 — Próximo trecho.** Dada a posição de escuta, o próximo trecho a transcrever é:
  (a) a própria posição, se ela não estiver coberta; senão
  (b) o fim do intervalo coberto que contém a posição; e, se dali até o fim do áudio
  tudo já estiver coberto,
  (c) o primeiro buraco desde o começo do áudio.
  Quando o áudio inteiro está coberto, não há próximo trecho.
- **T4 — Formato antigo.** Arquivos no formato de capítulo inteiro (`{"chapter": {...},
  "words": [...]}`) são aceitos como pedaços.
- **T5 — Palavras sem duplicata.** A lista completa de palavras sai ordenada por tempo,
  e palavras repetidas por pedaços sobrepostos aparecem uma vez só.
- **T6 — Arquivos corrompidos** (por exemplo, gravação interrompida) são ignorados
  na leitura.
