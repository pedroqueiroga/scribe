# Plataforma e dependências

Testes: [`tests/test_plataforma.py`](../tests/test_plataforma.py)

- **K1 — Sessões longas.** O app precisa rodar por horas, já que um audiobook dura horas.
  Nenhuma dependência pode ter defeito que se acumule com o tempo. Em particular, o
  PySide6 6.12.0 tem um defeito no `Signal.emit()` que consome uma referência do `True` a
  cada emissão. No Python 3.11, isso derruba o processo depois de cerca de um minuto de
  interface aberta. A versão instalada precisa emitir sinais sem alterar a contagem de
  referências.
