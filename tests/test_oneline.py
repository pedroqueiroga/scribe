"""Modo de uma linha — specs/oneline.md (O1–O6).

As funções recebem a altura de uma linha medida na tela (em px)."""
from __future__ import annotations

import math

import pytest

from scribe.oneline import (DOCK, ESTIMATE, estimated_line, height_after_line_change,
                            initial_height, is_oneline, oneline_height, threshold)


# ---------------------------------------------------------------- O1

@pytest.mark.parametrize("line", [20.47, 37.11, 108.8])
def test_O1_altura_de_uma_linha(line):
    assert oneline_height(line) == math.ceil(line + 22)


def test_O1_estimativa_enquanto_a_medida_nao_chega():
    assert estimated_line(22) == pytest.approx(22 * ESTIMATE)
    assert ESTIMATE == pytest.approx(1.7)


# ---------------------------------------------------------------- O2

@pytest.mark.parametrize("line", [20.47, 37.11, 67.83])
def test_O2_limite_entre_os_modos(line):
    t = threshold(line)
    assert t == pytest.approx(DOCK + 2.5 * line)
    assert is_oneline(t - 1, line)
    assert not is_oneline(t, line)
    assert not is_oneline(t + 100, line)


def test_O2_o_limite_acompanha_a_altura_da_linha():
    # a mesma janela de 120 px é uma linha com linhas grandes e normal com linhas pequenas
    assert is_oneline(120, 37.11)       # fonte 22
    assert not is_oneline(120, 20.47)   # fonte 12


# ---------------------------------------------------------------- O3

@pytest.mark.parametrize("line", [x / 2 for x in range(10, 240)])
def test_O3_altura_de_uma_linha_fica_abaixo_do_limite(line):
    assert is_oneline(oneline_height(line), line)


# ---------------------------------------------------------------- O4

def test_O4_no_modo_de_uma_linha_a_altura_acompanha_a_linha():
    h = oneline_height(37.11)
    assert height_after_line_change(h, 37.11, 47.36) == oneline_height(47.36)
    assert height_after_line_change(h, 37.11, 20.47) == oneline_height(20.47)


def test_O4_no_modo_normal_a_altura_nao_muda():
    assert height_after_line_change(400, 37.11, 47.36) == 400


# ---------------------------------------------------------------- O5

def test_O5_flag_oneline_chega_a_janela(monkeypatch):
    import scribe.cli as cli
    import scribe.overlay as overlay
    calls = []
    monkeypatch.setattr(overlay, "main", lambda paths, model, oneline=False, **kw: calls.append((paths, oneline)))
    cli.main(["play", "livro", "--oneline"])
    cli.main(["play", "livro"])
    assert calls == [(["livro"], True), (["livro"], False)]


def test_O5_flag_abre_na_altura_de_uma_linha():
    assert initial_height(saved=300, line=37.11, oneline=True) == oneline_height(37.11)
    assert initial_height(saved=300, line=37.11, oneline=False) == 300
    assert initial_height(saved=None, line=37.11, oneline=False) is None


# ---------------------------------------------------------------- O6

def test_O6_a_faixa_tem_exatamente_a_altura_de_uma_linha():
    from scribe.oneline import strip_margins
    for line in (20.47, 37.11, 108.8):
        h = oneline_height(line)
        top, bottom = strip_margins(h, line)
        assert h - top - bottom == pytest.approx(line)
        assert top >= 0 and bottom >= 4          # a linha de progresso fica embaixo
