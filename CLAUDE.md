# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

O scribe junta um EPUB e o audiobook do mesmo livro num overlay translúcido (PySide6/QML,
X11) com o texto sincronizado à narração palavra por palavra. Visão geral, princípios
(P1–P4) e índice dos componentes ficam em [SPEC.md](SPEC.md). Converse e escreva specs em
português.

## Comandos

```bash
.venv/bin/pytest                                   # suíte completa
.venv/bin/pytest tests/test_align.py -k A9         # requisitos específicos (pelo código)
.venv/bin/pytest tests/test_spec_coverage.py       # todo requisito tem teste?
.venv/bin/scribe play <livro|nº|pasta|epub/txt áudio> [--oneline] [--full]
.venv/bin/scribe list
.venv/bin/scribe prepare <livro>                   # transcreve e alinha tudo de antemão
```

`tests/test_atalhos.py` só roda com `DISPLAY` definido. Dependências de sistema: libmpv2
(python-mpv). Pergunte antes de instalar qualquer pacote do sistema, nomeando o pacote e
justificando. O PySide6 6.12.0 está excluído no `pyproject.toml` (bug de refcount no
`Signal.emit`, coberto pelo K1); não remova essa restrição.

## Fluxo de trabalho: spec → testes → código

Os specs (`SPEC.md` + `specs/*.md`, um por componente, prosa estruturada em português) são
a **fonte única da verdade**. Cada requisito tem um código em negrito (`**A9 — ...**`):
E/N epub, T store, W worker, A align, S session, L library, R reader, G layout, H atalhos,
O oneline, K plataforma, J janela.

Para qualquer mudança de comportamento:

1. Atualize ou crie o requisito no spec.
2. Escreva o teste citando o código no nome (`test_A9_...`) ou na docstring, e confirme
   que ele **falha** antes de implementar. Um requisito pode ter vários testes.
3. Implemente e rode a suíte inteira.
4. Se o código ganhar um comportamento que não está no spec, acrescente o requisito.

`tests/test_spec_coverage.py` falha se um requisito automático não tiver teste ou se um
teste citar um código inexistente. Specs com *(manual)* na primeira linha (hoje só
`specs/janela.md`, J) ficam de fora: são verificados rodando o app.

Práticas que se mostraram necessárias:

- **Teste de mutação manual.** Depois que os testes passam, quebre cada regra no código
  (com backup no scratchpad) e confira se algum teste falha. Desconfie de testes que passam
  de primeira; já houve testes passando pelo motivo errado. Por exemplo, o `build()`
  narrava um parágrafo que o teste supunha não narrado; passe `transcript=narrate(...)`
  explicitamente.
- **Fixtures sempre sintéticas** (`tests/conftest.py`: `make_epub`, PNG;
  `tests/helpers.py`: `make_book`, `narrate`, `speak`). Nunca use o livro e o áudio do
  usuário na raiz do repo nos testes, porque são protegidos por direitos autorais e estão
  no `.gitignore`.
- **Calibre critérios heurísticos com os dados reais**, rodando o detector no livro de
  verdade fora dos testes (foi assim que se escolheu o limiar de 0,7 do A12). Depois fixe
  o resultado num teste sintético.
- **Meça antes de corrigir.** Instrumente, reproduza com uma cópia dos dados reais e
  isole num exemplo mínimo.

## Arquitetura

```
EPUB ─► epub ─► blocos/palavras ────────────────┐
áudio ─► worker ─► pedaços ─► store ─► align ─► session ─► reader ─► overlay (Bridge + QML)
           ▲                                                  │
           └─────────── posição de escuta ◄───────────────────┘
```

- **Toda a lógica é pura, com dependências injetadas.** Por isso é testável sem Qt, mpv
  ou Whisper. O worker roda via `transcribe_loop(store, duration, get_cmds, transcribe,
  emit)`, com um Whisper falso nos testes. `Session(book, cache, duration,
  audio_chapters)` tem `Session.open(...)` para os arquivos reais e recebe mensagens do
  worker por `handle(msg)`. `Reader` recebe o tocador (`FakePlayer` nos testes). Geometria
  e layout ficam em funções puras (`layout.ImageLayout`, `oneline.*`).
- **O overlay deve continuar fino.** `overlay.py` (`MpvPlayer`, `BlockModel` e `Bridge`
  com propriedades e slots Qt) e `overlay.qml` só repassam para o `Reader`, o `layout` e
  o `oneline`. Lógica nova vai para esses módulos puros, com spec e teste.
- **Streaming.** O worker é um processo em spawn, ligado por filas. Ele prioriza a
  posição de escuta (pedaço urgente de 7 s, normais de 24 s, sobreposição de 2 s) e
  interrompe o pedaço quando o foco muda. O `store` grava cada pedaço atomicamente. O
  `align` localiza cada pedaço novo no livro por votação de trigramas e realinha só
  aquela região (A8–A10). Cada palavra fica narrada, pulada ou **pendente**: nunca
  interpole atravessando um buraco de transcrição (P4).
- **O texto exibido é o do livro (P1).** A única exceção é o "texto só do áudio" (A12),
  que exige todas as seis condições do spec.
- **Modo completo** (C, `specs/completo.md`): `full.py` gera do EPUB (ou TXT, `txt.py`)
  uma página HTML única em `books/<sha1>/full/`, com `data-b` em cada bloco e os trechos
  das palavras em `data-w="id:início:fim"`. `scribe.js` pinta o marca-texto com a CSS
  Custom Highlight API e fala com o QML por `console.log("scribe:…")`. A view fica em
  `fullpage.qml`, separada, para o overlay não depender do QtWebEngine.
- **Biblioteca** em `~/.local/share/scribe` (XDG): `library.json`, `books/<sha1>/`
  (transcrição e cache) e `backgrounds/`. As preferências da janela ficam salvas pelo
  `Reader`.

## Verificação visual (requisitos J, manuais)

O que é visual é verificado no display X11 real, com scripts descartáveis no scratchpad:
tocador falso, ou o app real com a biblioteca copiada para um `XDG_DATA_HOME` temporário,
capturando quadros com `QQuickWindow.grabWindow`. O que já custou caro:

- Use `QT_QPA_PLATFORM=xcb`. No offscreen os shaders do MultiEffect não rodam e o
  `grabWindow` trava. Importe `PySide6.QtQuick` para ter o `grabWindow`.
- Nunca bloqueie o laço de eventos (nada de `xdotool sleep` ou `time.sleep`); use `QTimer`.
- Ponha a janela de teste longe da instância do usuário, porque a janela fixa dele captura
  os eventos. Restaure a posição do cursor ao terminar.
- Use `timeout -s KILL` e evite padrões de `pkill` que casem com o próprio comando.
- Nunca automatize o FileDialog com xdotool: isso prende o portal do GNOME.
- Alguns crashes só aparecem com áudio real (PulseAudio), não com `ao=null`.
- Modo completo: um `<span>` por palavra (30 mil) deixava a página segundos mais lenta;
  por isso os trechos ficam no bloco. Destruir o WebEngineView com o livro carregado e a
  acessibilidade ligada inunda a fila de eventos e trava o processo: antes de destruir, a
  view vai para `about:blank` (fechar e voltar ao overlay passam por isso). O Chromium não
  redesenha janelas fora da tela, e o `grabWindow` às vezes trava com ele: capture com
  `import -window <winId>`. No GNOME o xdotool não muda o foco; teclas e cliques de teste
  vão por `QTest.keyClick`/`mouseClick` na janela.
- No QML, chamadas que reposicionam a lista a partir de delegates devem ser adiadas com
  `Qt.callLater`, porque as síncronas causaram segfault em pulos rápidos. No encerramento
  a ordem é: pausar, parar os timers, salvar, parar o worker, fechar o player e destruir
  os objetos raiz antes do motor QML.

## Git

O branch principal é `main`. Só faça commit quando for pedido.
