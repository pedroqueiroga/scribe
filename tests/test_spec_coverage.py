"""Os testes espelham os specs (SPEC.md e specs/*.md são a fonte única da verdade).

- Todo requisito automático dos specs tem pelo menos um teste que o cita.
- Nenhum teste cita um requisito que não existe.

Um teste cita um requisito pelo código no nome (test_A4_...) ou na docstring/comentário.
Requisitos de componentes marcados como *(manual)* no título ficam de fora.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQ = re.compile(r"\*\*([A-Z]\d+)\s+—")
CITE = re.compile(r"(?<![A-Za-z0-9])([A-Z]\d+)(?![0-9])")


def spec_requirements() -> dict[str, Path]:
    reqs = {}
    for path in [ROOT / "SPEC.md", *sorted((ROOT / "specs").glob("*.md"))]:
        text = path.read_text()
        manual_file = "*(manual)*" in text.splitlines()[0]
        for code in REQ.findall(text):
            if path.name == "SPEC.md" and code.startswith("P"):
                continue  # princípios: verificados através dos requisitos específicos
            if not manual_file:
                reqs[code] = path
    return reqs


def all_spec_codes() -> set[str]:
    codes = set()
    for path in [ROOT / "SPEC.md", *(ROOT / "specs").glob("*.md")]:
        codes |= set(REQ.findall(path.read_text()))
    return codes


def cited_in_tests() -> set[str]:
    cited = set()
    for path in (ROOT / "tests").glob("test_*.py"):
        if path.name != "test_spec_coverage.py":
            cited |= set(CITE.findall(path.read_text()))
    return cited


def test_todo_requisito_tem_teste():
    missing = sorted(set(spec_requirements()) - cited_in_tests(), key=lambda c: (c[0], int(c[1:])))
    assert not missing, f"requisitos sem teste: {missing}"


def test_testes_so_citam_requisitos_existentes():
    codes = all_spec_codes()
    # só olha códigos com prefixos usados nos specs, para não confundir com outras siglas
    prefixes = {c[0] for c in codes}
    unknown = sorted(c for c in cited_in_tests() if c[0] in prefixes and c not in codes)
    assert not unknown, f"testes citam requisitos inexistentes: {unknown}"
