# scribe

scribe sincroniza um áudio com o texto que está sendo falado nele (EPUB ou `.txt`):
enquanto o áudio toca, a palavra dita fica acesa, como num karaokê. Serve para um
audiobook, uma palestra com o roteiro, um poema declamado, um texto numa língua que você
está aprendendo.

Dá para acompanhar o texto de quatro jeitos:

- **Uma linha:** uma faixa fina, como uma legenda, só com a linha falada. Pode ficar na
  borda da tela, enquanto você faz outra coisa.
- **Normal:** alguns parágrafos, com o atual em destaque e as imagens do texto num
  painel ao lado.
- **Vertical:** uma coluna estreita, com as imagens no meio do texto.
- **Completo:** o texto inteiro como num leitor de e-book, com a formatação e as imagens
  originais e um marca-texto que segue o áudio.

Nos três primeiros, a janela é translúcida, pode ficar por cima das outras e pode deixar
os cliques passarem para o programa que está embaixo.

## 1. Instalação

Você vai precisar de Linux com **X11** (no Wayland ainda não funciona direito) e destes
pacotes do sistema:

- `libmpv2`, que toca o áudio;
- `ffmpeg`, usado para ler o áudio.

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

Na primeira vez que você abrir um áudio, scribe baixa o reconhecimento de voz que usa
para acompanhar a fala, o que leva alguns minutos.

## 2. Abrindo um texto

Passe o texto e o áudio, em qualquer ordem:

```bash
.venv/bin/scribe play texto.epub audio.m4b
```

Também dá para passar a pasta que tem os dois arquivos.

O áudio começa a tocar na hora. Nos primeiros segundos aparece o aviso "carregando o
modelo…" ou "transcrevendo…", e logo o texto surge sincronizado. scribe continua
trabalhando no resto do áudio enquanto você ouve e guarda o que já fez: se você fechar e
abrir de novo, ele continua de onde parou.

Depois da primeira vez, o texto fica guardado na biblioteca e você não precisa mais dos
caminhos:

```bash
.venv/bin/scribe play                 # reabre o último, na posição em que parou
.venv/bin/scribe play poemas          # um trecho do título ou do nome do arquivo
.venv/bin/scribe list                 # lista a biblioteca, com número e posição
.venv/bin/scribe play 2               # abre pelo número mostrado no list
```

Se você mover os arquivos para outra pasta, o progresso não se perde: o texto é
reconhecido pelo conteúdo.

### Preparar tudo de antemão (opcional)

```bash
.venv/bin/scribe prepare texto.epub audio.m4b
```

Esse comando sincroniza o áudio inteiro sem abrir janela. Assim, na hora de ouvir,
qualquer pulo já mostra o texto. Para uma sincronia mais precisa (e mais demorada de
preparar), use `--model medium`.

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
  palavra falada, clique na mira dourada que aparece na barra (ou dê qualquer pulo).
- **Arraste a alça dourada** na parede esquerda para escolher em que altura da janela a
  linha atual fica. Um clique duplo nela volta para 40%.

Para mexer na janela:

- **Arraste pelo fundo** para mover a janela e **pelas bordas** para redimensionar.
- **Fixar** deixa a janela por cima das outras e impede que ela seja movida ou
  redimensionada sem querer.
- **Atravessar cliques** faz os cliques passarem para o programa que está embaixo, para
  você usar o computador com o texto por cima. Só um cadeado aberto na parede esquerda
  continua clicável: clique nele (ou use Ctrl+Alt+F) para desligar.

As imagens do texto aparecem na hora em que o áudio chega nelas e somem sozinhas depois.

## 4. Os modos

O modo depende do tamanho da janela:

- **Uma linha:** se você deixar a janela bem baixa, ela vira uma faixa que mostra só a
  linha falada, como uma legenda. A barra aparece numa janelinha à parte, e as imagens
  viram uma miniatura na ponta (passe o mouse para ver a imagem grande). Para abrir já
  assim, use `scribe play --oneline`.
- **Normal:** vários parágrafos, com o atual em destaque e as imagens num painel ao lado.
- **Vertical:** se a janela for estreita, as imagens entram no meio do texto.
- **Completo:** o botão de livro aberto na barra (ou `scribe play --full`) mostra o
  texto inteiro como num leitor de e-book, com as fontes, os títulos e as imagens
  originais. A palavra falada ganha um marca-texto. A régua dourada no alto ajusta a
  largura e a posição da linha, e um botão na barra maximiza a janela.

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

Tudo fica em `~/.local/share/scribe/`: a biblioteca e as preferências (`library.json`),
o que scribe já sincronizou de cada texto (`books/`) e as imagens de fundo
(`backgrounds/`). Os seus arquivos de texto e de áudio não são alterados.

## 7. Quando algo não sai certo

- **O texto não aparece:** scribe ainda está acompanhando esse trecho do áudio. Espere
  alguns segundos ou rode `scribe prepare` antes de ouvir.
- **Um trecho ficou esmaecido:** essa parte do áudio ainda não foi sincronizada. scribe
  prefere deixar o trecho apagado a acender a palavra errada.
- **A sincronia parece estranha:** `scribe check <nome>` (com `-v` para mais detalhes)
  mostra um relatório de como o texto e o áudio estão batendo.
- **Um texto "sumiu" da biblioteca:** se você moveu ou renomeou os arquivos, a mensagem
  diz qual deles não foi encontrado. Abra de novo passando os caminhos novos.
