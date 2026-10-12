# scribe — especificação

O scribe junta um **EPUB** e o **audiobook** do mesmo livro para criar uma leitura
imersiva no computador. O texto do livro aparece numa janela translúcida, sincronizado
com a narração palavra por palavra, estilo karaoke.

Este arquivo reúne a visão geral e os princípios. Os requisitos ficam em `specs/`, um
arquivo por componente. Cada requisito tem um código (por exemplo **A4**), e o arquivo de
teste pareado cita esse código nos testes que o verificam. Um requisito marcado como
*(manual)* é conferido rodando o app.

## Princípios

- **P1 — O texto exibido é o do livro.** A transcrição automática serve para descobrir
  *quando* cada palavra é dita. Há uma exceção: um trecho que o narrador fala e que
  **realmente não existe no livro** (por exemplo, o texto de uma imagem lido em voz alta)
  aparece, marcado como vindo do áudio, desde que a transcrição tenha confiança alta
  (**A12**, em [specs/align.md](specs/align.md)).
- **P2 — Não esperar.** O áudio começa a tocar assim que o livro abre. A legenda aparece
  assim que o trecho atual for transcrito, o que deve levar poucos segundos.
- **P3 — Nada se perde.** Todo trecho transcrito é salvo em disco no momento em que fica
  pronto. Ao reabrir o livro, o trabalho continua de onde parou.
- **P4 — Não inventar.** Se ainda não há transcrição de um trecho do áudio, o texto
  correspondente fica *pendente*. O programa não chuta tempos atravessando um buraco.

## Como as peças se encaixam

```
EPUB ──► epub ──► blocos e palavras ─────────────┐
                                                 ▼
áudio ─► worker ─► pedaços ─► store ──► align ──► session ──► reader ──► janela
           ▲                                                   │
           └────────────── posição de escuta ◄─────────────────┘
```

## Componentes

| Prefixo | Componente                  | Spec                                     | Testes                                         |
|---------|-----------------------------|------------------------------------------|------------------------------------------------|
| E, N    | Extração do EPUB            | [specs/epub.md](specs/epub.md)           | [tests/test_epub.py](tests/test_epub.py)       |
| T       | Armazenamento da transcrição | [specs/store.md](specs/store.md)        | [tests/test_store.py](tests/test_store.py)     |
| W       | Transcrição em streaming    | [specs/worker.md](specs/worker.md)       | [tests/test_worker.py](tests/test_worker.py)   |
| A       | Alinhamento                 | [specs/align.md](specs/align.md)         | [tests/test_align.py](tests/test_align.py)     |
| S       | Sessão e linha do tempo     | [specs/session.md](specs/session.md)     | [tests/test_session.py](tests/test_session.py) |
| L       | Biblioteca                  | [specs/library.md](specs/library.md)     | [tests/test_library.py](tests/test_library.py) |
| R       | Leitor                      | [specs/reader.md](specs/reader.md)       | [tests/test_reader.py](tests/test_reader.py)   |
| G       | Imagem ao lado do texto  | [specs/layout.md](specs/layout.md) | [tests/test_layout.py](tests/test_layout.py) |
| H       | Atalhos globais           | [specs/atalhos.md](specs/atalhos.md) | [tests/test_atalhos.py](tests/test_atalhos.py) |
| O       | Modo de uma linha        | [specs/oneline.md](specs/oneline.md) | [tests/test_oneline.py](tests/test_oneline.py) |
| K       | Plataforma e dependências | [specs/plataforma.md](specs/plataforma.md) | [tests/test_plataforma.py](tests/test_plataforma.py) |
| J       | Janela *(manual)*           | [specs/janela.md](specs/janela.md)       | —                                              |

## Rodando os testes

```bash
.venv/bin/pytest
```
