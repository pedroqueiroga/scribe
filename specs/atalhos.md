# Atalhos globais (`scribe/hotkeys.py`)

Testes: [`tests/test_atalhos.py`](../tests/test_atalhos.py)

As combinações e o que cada uma faz estão em **J8** ([janela.md](janela.md)). No X11, cada
combinação é registrada de forma exclusiva: enquanto o scribe está aberto, ela não chega a
outros programas.

- **H1 — Falhas com nome.** Se uma combinação não puder ser registrada (porque outro
  programa já a usa, por exemplo outra janela do scribe aberta), ela aparece pelo nome na
  lista de falhas, e o aviso no terminal diz qual foi. As outras combinações continuam
  registradas normalmente.
