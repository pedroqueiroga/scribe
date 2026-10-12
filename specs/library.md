# Biblioteca (`scribe/library.py`)

Testes: [`tests/test_library.py`](../tests/test_library.py)

A biblioteca é o registro interno do scribe: todo livro aberto com `scribe play` ou
preparado com `scribe prepare` fica registrado, com os caminhos absolutos dos arquivos.
Depois disso, o livro pode ser chamado de qualquer pasta, só pelo nome.

- **L1 — Argumentos.** `scribe play` e `scribe prepare` aceitam o EPUB e o áudio em
  qualquer ordem, ou uma pasta que contenha os dois. Cada arquivo é reconhecido pela
  extensão. Caminhos relativos são resolvidos a partir da pasta atual e guardados como
  absolutos.
- **L2 — Memória do par.** Depois da primeira vez, basta o EPUB: o áudio é lembrado.
- **L3 — Último livro.** Sem argumentos, `scribe play` reabre o último livro aberto.
- **L4 — Identidade.** Um livro é identificado pelo conteúdo do EPUB, não pelo caminho.
  Mover o arquivo de lugar não perde o progresso.
- **L5 — Cache fora da pasta do livro.** O cache fica em `$XDG_DATA_HOME/scribe/books/<id>/`,
  com `~/.local/share` como padrão.
- **L6 — Posição.** A posição de escuta é salva periodicamente e ao fechar. Ao reabrir,
  o livro continua dali.
- **L7 — Erros claros.** Faltar o EPUB, faltar o áudio na primeira vez, ou passar arquivo
  inexistente gera uma mensagem explicando o que fazer.
- **L8 — Cache antigo.** Se existir uma pasta `<livro>.scribe/` ao lado do EPUB (formato
  das primeiras versões), ela é movida para o cache da biblioteca na primeira abertura,
  para não perder transcrição já feita. Se o cache da biblioteca já tiver transcrição,
  nada é movido.
- **L9 — Listagem.** `scribe list` mostra todos os livros registrados, do aberto mais
  recentemente para o mais antigo. Cada linha traz um número, o título, a posição de
  escuta e o caminho do EPUB. O último livro aberto é marcado.
- **L10 — Chamar pelo nome.** Um argumento que não é um arquivo existente é procurado entre
  os livros registrados, de qualquer pasta. Ele casa com o nome do arquivo EPUB (com ou sem
  extensão) ou com um trecho do título, sem diferenciar maiúsculas nem acentos. Também
  pode ser o número mostrado por `scribe list`. Arquivos existentes têm prioridade.
  - Se mais de um livro casar, o comando lista os candidatos e pede um nome mais
    específico. Um nome que é exatamente o nome do arquivo de um único livro vence os
    casamentos parciais.
  - Se nenhum casar, a mensagem sugere `scribe list`.
  - Se o EPUB ou o áudio registrados não existirem mais no caminho guardado, a mensagem
    diz qual arquivo sumiu e como registrar o novo caminho.
