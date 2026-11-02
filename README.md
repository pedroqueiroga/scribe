# scribe

O scribe toca o audiobook e mostra o texto do EPUB numa janela translúcida, com a
palavra narrada acesa, como num karaokê. Você pode deixar a janela num canto da tela
enquanto faz outra coisa, ou abrir o livro inteiro e ler junto com a narração.

## 1. Instalação

Você vai precisar de Linux com **X11** (no Wayland ainda não funciona direito) e destes
pacotes do sistema:

- `libmpv2`, que toca o áudio;
- `ffmpeg`, que fornece o `ffprobe` e o `ffmpeg`, usados para ler o áudio.

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

Na primeira vez que o scribe transcrever um livro, ele baixa o modelo do Whisper
(`small`, por padrão), o que leva alguns minutos.

## 2. Abrindo um livro

Passe o EPUB e o áudio, em qualquer ordem:

```bash
.venv/bin/scribe play livro.epub audiobook.m4b
```

Também dá para passar a pasta que tem os dois arquivos. O livro pode ser um `.txt` em
vez de EPUB.

O áudio começa a tocar na hora. Por alguns segundos, enquanto o trecho atual é
transcrito, aparece o aviso "carregando o modelo…" ou "transcrevendo…", e depois o texto
surge sincronizado. A transcrição continua em segundo plano e é salva aos poucos: se
você fechar o app, ela retoma de onde parou na próxima vez.

Depois da primeira vez, o scribe guarda o livro na biblioteca dele e você não precisa
mais dos caminhos:

```bash
.venv/bin/scribe play                 # reabre o último livro, na posição em que parou
.venv/bin/scribe play drowning        # um trecho do título ou do nome do arquivo
.venv/bin/scribe list                 # lista os livros, com número e posição
.venv/bin/scribe play 2               # abre pelo número mostrado no list
```

Se você mover o EPUB para outra pasta, o progresso não se perde: o livro é reconhecido
pelo conteúdo.

### Transcrever tudo de antemão (opcional)

```bash
.venv/bin/scribe prepare livro.epub audiobook.m4b
```

Esse comando transcreve e alinha o livro inteiro sem abrir janela. Assim, na hora de
ouvir, pulos para qualquer ponto já mostram o texto. Para um modelo mais preciso (e mais
lento), use `--model medium`.

## 3. A janela

Passe o mouse pela janela para aparecer a **barra** na parte de baixo. Os controles são
ícones; pare o mouse em cima de um por meio segundo para ver o nome dele. A barra traz:

- o capítulo atual e a linha de progresso (clique ou arraste para pular);
- voltar e avançar 10 s, e tocar/pausar;
- a velocidade (de 0,75× a 2×);
- o tamanho e a cor da letra, a opacidade e o fundo (uma cor ou uma imagem);
- **fixar**, **atravessar cliques**, **modo completo** e fechar.

Para mexer no texto:

- **Clique numa palavra** para levar o áudio até ela.
- **Role com o mouse** para ler à frente ou voltar sem mexer no áudio. Para voltar à
  palavra narrada, clique na mira dourada que aparece na barra (ou dê qualquer pulo).
- **Arraste a alça dourada** na parede esquerda para escolher em que altura da janela a
  linha atual fica. Um clique duplo nela volta para 40%.

Para mexer na janela:

- **Arraste pelo fundo** para mover a janela e **pelas bordas** para redimensionar.
- **Fixar** deixa a janela por cima das outras e impede que ela seja movida ou
  redimensionada sem querer.
- **Atravessar cliques** faz os cliques passarem para o programa que está embaixo, para
  você usar o computador com o texto por cima. Só um cadeado aberto na parede esquerda
  continua clicável: clique nele (ou use Ctrl+Alt+F) para desligar.

As imagens do livro aparecem ao lado do texto na hora em que são narradas e somem
sozinhas depois.

## 4. Os modos

O modo depende do tamanho da janela:

- **Normal:** vários parágrafos, com o atual em destaque e as imagens num painel ao lado.
- **Uma linha:** se você deixar a janela bem baixa, ela vira uma faixa que mostra só a
  linha narrada, como uma legenda. A barra aparece numa janelinha à parte, e as imagens
  viram uma miniatura na ponta (passe o mouse para ver a imagem grande). Para abrir já
  assim, use `scribe play --oneline`.
- **Vertical:** se a janela for estreita, as imagens entram no meio do texto.
- **Completo:** o botão de livro aberto na barra (ou `scribe play --full`) mostra o livro
  inteiro como num leitor de e-book, com as fontes, os títulos e as imagens originais. A
  palavra narrada ganha um marca-texto. A régua dourada no alto ajusta a largura e a
  posição da linha, e um botão na barra maximiza a janela.

## 5. Atalhos

Com a janela em foco:

| Tecla   | Ação                        |
|---------|-----------------------------|
| Espaço  | tocar / pausar              |
| ← / →   | voltar / avançar 10 s       |
| ↑ / ↓   | parágrafo anterior / próximo |
| Esc     | esconder                    |

Os atalhos globais funcionam de qualquer programa:

| Atalho          | Ação                         |
|-----------------|------------------------------|
| Ctrl+Alt+P      | tocar / pausar               |
| Ctrl+Alt+, / .  | voltar / avançar 10 s        |
| Ctrl+Alt+J / K  | parágrafo anterior / próximo |
| Ctrl+Alt+[ / ]  | mais devagar / mais rápido   |
| Ctrl+Alt+H      | mostrar / esconder a janela  |
| Ctrl+Alt+F      | fixar / soltar               |

Se outro programa já usa uma dessas combinações, o terminal avisa qual delas não foi
registrada. As outras continuam funcionando.

## 6. Onde ficam as coisas

Tudo fica em `~/.local/share/scribe/`: a lista de livros e as preferências
(`library.json`), a transcrição e o cache de cada livro (`books/`) e as imagens de fundo
(`backgrounds/`). Os seus arquivos de EPUB e de áudio não são alterados.

## 7. Quando algo não sai certo

- **O texto não aparece:** o trecho ainda está sendo transcrito. Espere alguns segundos
  ou rode `scribe prepare` antes de ouvir.
- **Um trecho ficou esmaecido:** essa parte do áudio ainda não foi transcrita. O scribe
  prefere não mostrar a sincronia a inventar um tempo.
- **A sincronia parece estranha:** `scribe check <livro>` (com `-v` para mais detalhes)
  mostra um relatório da qualidade do alinhamento.
- **O livro "sumiu":** se você moveu ou renomeou os arquivos, a mensagem diz qual deles
  não foi encontrado. Abra de novo passando os caminhos novos.
