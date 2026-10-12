"""Biblioteca — specs/library.md (L1–L8)."""
from __future__ import annotations

import pytest

from scribe.library import Library


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Biblioteca isolada em tmp/data; livros em tmp/livros."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    books = tmp_path / "livros"
    books.mkdir()
    return books


def touch(path, content=b"conteudo"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# ---------------------------------------------------------------- L1

def test_L1_epub_e_audio_em_qualquer_ordem(home):
    ep = touch(home / "livro.epub", b"epub-1")
    au = touch(home / "audio.m4b")
    bid_a, e_a = Library().resolve([str(ep), str(au)])
    bid_b, e_b = Library().resolve([str(au), str(ep)])
    assert bid_a == bid_b
    assert e_a["epub"] == e_b["epub"] == str(ep)
    assert e_a["audio"] == e_b["audio"] == str(au)


def test_L1_pasta_com_os_dois_arquivos(home):
    ep = touch(home / "pasta" / "livro.epub", b"epub-1")
    au = touch(home / "pasta" / "livro.mp3")
    touch(home / "pasta" / "capa.jpg")
    _, e = Library().resolve([str(home / "pasta")])
    assert e["epub"] == str(ep) and e["audio"] == str(au)


@pytest.mark.parametrize("ext", [".m4b", ".m4a", ".mp3", ".ogg", ".opus", ".flac", ".wav"])
def test_L1_extensoes_de_audio_reconhecidas(home, ext):
    ep = touch(home / "livro.epub", b"epub-1")
    au = touch(home / f"audio{ext}")
    _, e = Library().resolve([str(ep), str(au)])
    assert e["audio"] == str(au)


# ---------------------------------------------------------------- L2

def test_L2_depois_da_primeira_vez_basta_o_epub(home):
    ep = touch(home / "livro.epub", b"epub-1")
    au = touch(home / "audio.m4b")
    lib = Library()
    bid, _ = lib.resolve([str(ep), str(au)])
    lib.touch(bid)
    _, e = Library().resolve([str(ep)])
    assert e["audio"] == str(au)


# ---------------------------------------------------------------- L3

def test_L3_sem_argumentos_reabre_o_ultimo_livro(home):
    lib = Library()
    for name in ("um", "dois"):
        bid, _ = lib.resolve([str(touch(home / f"{name}.epub", name.encode())),
                              str(touch(home / f"{name}.m4b"))])
        lib.touch(bid)
    bid, e = Library().resolve([])
    assert e["epub"] == str(home / "dois.epub")


# ---------------------------------------------------------------- L4

def test_L4_mover_o_epub_mantem_o_mesmo_livro(home):
    ep = touch(home / "livro.epub", b"epub-1")
    au = touch(home / "audio.m4b")
    lib = Library()
    bid, _ = lib.resolve([str(ep), str(au)])
    lib.set_position(bid, 321.0)
    moved = ep.rename(home / "outro-nome.epub")
    bid2, e = Library().resolve([str(moved)])
    assert bid2 == bid
    assert e["position"] == 321.0
    assert e["epub"] == str(moved)


def test_L4_epubs_diferentes_sao_livros_diferentes(home):
    a = touch(home / "a.epub", b"epub-a")
    b = touch(home / "b.epub", b"epub-b")
    au = touch(home / "audio.m4b")
    assert Library().resolve([str(a), str(au)])[0] != Library().resolve([str(b), str(au)])[0]


# ---------------------------------------------------------------- L5

def test_L5_cache_fica_no_diretorio_de_dados(home, tmp_path):
    lib = Library()
    bid, _ = lib.resolve([str(touch(home / "l.epub")), str(touch(home / "l.m4b"))])
    assert lib.cache(bid) == tmp_path / "data" / "scribe" / "books" / bid
    assert lib.cache(bid).is_dir()
    assert not (home / "l.scribe").exists()


def test_L5_padrao_e_local_share(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    from scribe.library import data_dir
    assert data_dir() == tmp_path / ".local" / "share" / "scribe"


# ---------------------------------------------------------------- L6

def test_L6_posicao_salva_e_restaurada(home):
    lib = Library()
    bid, e = lib.resolve([str(touch(home / "l.epub")), str(touch(home / "l.m4b"))])
    assert e["position"] == 0.0
    lib.set_position(bid, 1234.567)
    _, e = Library().resolve([str(home / "l.epub")])
    assert e["position"] == pytest.approx(1234.57)


# ---------------------------------------------------------------- L7

def test_L7_sem_epub(home):
    with pytest.raises(SystemExit, match="epub"):
        Library().resolve([str(touch(home / "a.m4b"))])


def test_L7_audio_faltando_na_primeira_vez(home):
    with pytest.raises(SystemExit, match="áudio"):
        Library().resolve([str(touch(home / "l.epub"))])


def test_L7_arquivo_inexistente(home):
    with pytest.raises(SystemExit, match="Não encontrei"):
        Library().resolve([str(home / "nao-existe.epub")])


def test_L7_nenhum_livro_ainda(home):
    with pytest.raises(SystemExit, match="Nenhum livro"):
        Library().resolve([])


# ---------------------------------------------------------------- L8

def test_L8_cache_antigo_ao_lado_do_epub_e_movido(home):
    ep = touch(home / "livro.epub")
    touch(home / "livro.scribe" / "transcript" / "000.json", b"{}")
    lib = Library()
    bid, _ = lib.resolve([str(ep), str(touch(home / "a.m4b"))])
    assert (lib.cache(bid) / "transcript" / "000.json").exists()
    assert not (home / "livro.scribe").exists()


def test_L8_nao_sobrescreve_cache_com_transcricao(home):
    ep = touch(home / "livro.epub")
    au = touch(home / "a.m4b")
    lib = Library()
    bid, _ = lib.resolve([str(ep), str(au)])
    touch(lib.cache(bid) / "transcript" / "novo.json", b"{}")
    touch(home / "livro.scribe" / "transcript" / "velho.json", b"{}")
    Library().resolve([str(ep)])
    assert (lib.cache(bid) / "transcript" / "novo.json").exists()
    assert not (lib.cache(bid) / "transcript" / "velho.json").exists()
    assert (home / "livro.scribe").exists()


# ---------------------------------------------------------------- L1 (caminhos)

def test_L1_caminho_relativo_e_guardado_como_absoluto(home, monkeypatch):
    touch(home / "sub" / "livro.epub")
    touch(home / "sub" / "a.m4b")
    monkeypatch.chdir(home)
    _, e = Library().resolve(["sub/livro.epub", "sub/a.m4b"])
    assert e["epub"] == str(home / "sub" / "livro.epub")
    assert e["audio"] == str(home / "sub" / "a.m4b")


# ---------------------------------------------------------------- L9

def register(lib, home, name, title=None, position=0.0):
    ep = touch(home / f"{name}.epub", name.encode())
    au = touch(home / f"{name}.m4b")
    bid, _ = lib.resolve([str(ep), str(au)])
    lib.touch(bid, title=title or name)
    if position:
        lib.set_position(bid, position)
    return bid


def test_L9_lista_do_mais_recente_para_o_mais_antigo_com_o_ultimo_marcado(home):
    lib = Library()
    a = register(lib, home, "alfa", "Livro Alfa", position=3725.0)
    b = register(lib, home, "beta", "Livro Beta")
    rows = Library().books()
    assert [r["bid"] for r in rows] == [b, a]
    assert [r["num"] for r in rows] == [1, 2]
    assert [r["last"] for r in rows] == [True, False]
    assert rows[1]["title"] == "Livro Alfa"
    assert rows[1]["position"] == 3725.0
    assert rows[1]["epub"] == str(home / "alfa.epub")


def test_L9_scribe_list_imprime_os_livros(home, capsys):
    lib = Library()
    register(lib, home, "alfa", "Livro Alfa", position=3725.0)
    register(lib, home, "beta", "Livro Beta")
    from scribe.cli import main
    main(["list"])
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if "Livro" in l]
    assert "Livro Beta" in lines[0] and "*" in lines[0]          # último aberto, marcado
    assert "Livro Alfa" in lines[1] and "1:02:05" in lines[1]    # posição
    assert str(home / "alfa.epub") in lines[1]


def test_L9_lista_vazia_explica_como_comecar(home, capsys):
    from scribe.cli import main
    main(["list"])
    assert "scribe play" in capsys.readouterr().out


# ---------------------------------------------------------------- L10

@pytest.fixture
def two_books(home, tmp_path, monkeypatch):
    lib = Library()
    register(lib, home, "how-to-keep-house", "How to Keep House While Drowning")
    register(lib, home, "coracao", "O Coração das Trevas")
    elsewhere = tmp_path / "outro-lugar"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    return lib


@pytest.mark.parametrize("name", [
    "how-to-keep-house",           # nome do arquivo, sem extensão
    "how-to-keep-house.epub",      # com extensão
    "keep house",                  # trecho do título
    "KEEP HOUSE",                  # maiúsculas
])
def test_L10_chamar_pelo_nome_de_qualquer_pasta(two_books, home, name):
    _, e = Library().resolve([name])
    assert e["epub"] == str(home / "how-to-keep-house.epub")


def test_L10_sem_acentos(two_books, home):
    _, e = Library().resolve(["coração"])
    assert e["epub"] == str(home / "coracao.epub")
    _, e = Library().resolve(["coracao das"])
    assert e["epub"] == str(home / "coracao.epub")


def test_L10_pelo_numero_da_lista(two_books, home):
    rows = Library().books()
    _, e = Library().resolve([str(rows[1]["num"])])
    assert e["epub"] == rows[1]["epub"]


def test_L10_ambiguo_lista_os_candidatos(two_books):
    with pytest.raises(SystemExit) as exc:
        Library().resolve(["o"])
    msg = str(exc.value)
    assert "How to Keep House While Drowning" in msg and "O Coração das Trevas" in msg


def test_L10_nome_exato_do_arquivo_vence_casamento_parcial(home, tmp_path, monkeypatch):
    lib = Library()
    register(lib, home, "duna", "Duna")
    register(lib, home, "duna-messias", "Duna: Messias")
    monkeypatch.chdir(tmp_path)
    _, e = Library().resolve(["duna"])
    assert e["epub"] == str(home / "duna.epub")


def test_L10_nenhum_casa_sugere_scribe_list(two_books):
    with pytest.raises(SystemExit, match="scribe list"):
        Library().resolve(["guerra e paz"])


def test_L10_arquivo_registrado_que_sumiu(two_books, home):
    (home / "coracao.m4b").unlink()
    with pytest.raises(SystemExit) as exc:
        Library().resolve(["coracao"])
    msg = str(exc.value)
    assert str(home / "coracao.m4b") in msg and "scribe play" in msg


def test_L10_arquivo_existente_tem_prioridade_sobre_nome(two_books, home, tmp_path):
    # existe na pasta atual um epub chamado "coracao.epub" diferente do registrado
    local = touch(tmp_path / "outro-lugar" / "coracao.epub", b"outro conteudo")
    touch(tmp_path / "outro-lugar" / "coracao.m4b")
    _, e = Library().resolve(["coracao.epub", "coracao.m4b"])
    assert e["epub"] == str(local)


def test_L1_scribe_prepare_tambem_registra_o_livro(home, epub_factory, monkeypatch):
    import scribe.cli as cli
    ep = epub_factory([("c.xhtml", "C", "<p>texto</p>")], title="Livro Preparado")
    au = touch(home / "a.m4b")
    calls = []
    monkeypatch.setattr(cli, "_transcribe_all", lambda *a, **k: calls.append("transcrever"))
    monkeypatch.setattr(cli, "_align_all", lambda *a, **k: calls.append("alinhar"))
    cli.main(["prepare", str(ep), str(au)])
    assert calls == ["transcrever", "alinhar"]
    rows = Library().books()
    assert [r["title"] for r in rows] == ["Livro Preparado"]
    assert rows[0]["audio"] == str(au)
