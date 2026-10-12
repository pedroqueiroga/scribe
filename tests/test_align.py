"""Alinhamento — specs/align.md (A1–A11)."""
from __future__ import annotations

import pytest

from scribe.align import NARRATED, PENDING, SKIPPED, Aligner
from tests.helpers import all_words, make_book, narrate

P1 = ("when you look at a very messy space it is easy to feel overwhelmed "
      "take a few minutes to speak some compassionate words to yourself")
P2 = ("there are actually only five things in any room trash dishes laundry "
      "things that have a place and things that do not have a place")
P3 = ("the first step is to take a trash bag and pick up all the trash "
      "throw it away into the bag and do not take the trash out yet")
JUNK = ("thank you for downloading this publisher ebook get a free ebook when you "
        "join our mailing list plus get updates on new releases deals recommended "
        "reads and more from the publisher click below to sign up and see terms")


def aligned(book, transcript, covers=lambda a, b: True):
    al = Aligner(book)
    al.align_all(transcript)
    al.compute(covers)
    return al


def ids_of(book, paragraph_index):
    return [w["id"] for w in book["chapters"][0]["blocks"][paragraph_index]["words"]]


def states(al, ids):
    return {al.state[k] for k in ids}


# ---------------------------------------------------------------- A1

def test_A1_narracao_identica_casa_todas_as_palavras_com_o_tempo_exato():
    book = make_book(P1, P2)
    tr = narrate(P1, 1.0, P2)
    al = aligned(book, tr)
    for w, spoken in zip(all_words(book), tr):
        assert al.state[w["id"]] == NARRATED
        assert al.ws[w["id"]] == pytest.approx(spoken["s"])
        assert al.we[w["id"]] == pytest.approx(spoken["e"])


def test_A1_pontuacao_e_maiusculas_no_livro_nao_atrapalham():
    book = make_book("When you look at a very messy space, it’s easy to feel overwhelmed.")
    tr = narrate("when you look at a very messy space its easy to feel overwhelmed")
    al = aligned(book, tr)
    assert states(al, ids_of(book, 0)) == {NARRATED}


# ---------------------------------------------------------------- A2

def test_A2_erros_de_reconhecimento_nao_quebram_o_alinhamento():
    book = make_book("by KC Davis " + P1)
    # "KC" ouvido como "Casey", "compassionate" com erro
    tr = narrate("by Casey Davis " + P1.replace("compassionate", "compassonite"))
    al = aligned(book, tr)
    words = all_words(book)
    assert states(al, [w["id"] for w in words]) == {NARRATED}
    kc = next(w for w in words if w["t"] == "KC")
    by = next(w for w in words if w["t"] == "by")
    davis = next(w for w in words if w["t"] == "Davis")
    assert al.ws[by["id"]] < al.ws[kc["id"]] < al.ws[davis["id"]]


# ---------------------------------------------------------------- A3

def test_A3_trecho_do_livro_nao_lido_entre_trechos_lidos_e_pulado():
    book = make_book(P1, JUNK, P2)
    tr = narrate(P1, 2.0, P2)
    al = aligned(book, tr)
    assert states(al, ids_of(book, 1)) == {SKIPPED}
    assert states(al, ids_of(book, 0)) == {NARRATED}
    assert states(al, ids_of(book, 2)) == {NARRATED}


def test_A3_texto_nao_lido_com_pausa_longa_continua_pulado():
    # a pausa longa não engana: o narrador não falou as palavras
    book = make_book(P1, JUNK, P2)
    tr = narrate(P1, 40.0, P2)
    al = aligned(book, tr)
    assert states(al, ids_of(book, 1)) == {SKIPPED}


def test_A3_vinheta_falada_no_lugar_do_texto_nao_conta_como_leitura():
    book = make_book(P1, JUNK, P2)
    tr = narrate(P1, "read by the author", P2)
    al = aligned(book, tr)
    assert states(al, ids_of(book, 1)) == {SKIPPED}


def test_A3_trecho_curto_sem_fala_entre_ancoras_e_interpolado():
    book = make_book(P1, "Chapter Two", P2)
    tr = narrate(P1, 1.0, P2)   # o título não foi reconhecido
    al = aligned(book, tr)
    assert states(al, ids_of(book, 1)) == {NARRATED}


def test_A3_texto_antes_da_primeira_ancora_e_pulado_se_o_audio_foi_transcrito():
    book = make_book(JUNK, P1)
    tr = narrate(3.0, P1)
    al = aligned(book, tr)
    assert states(al, ids_of(book, 0)) == {SKIPPED}


def test_A3_texto_depois_da_ultima_ancora_e_pulado_se_o_audio_foi_transcrito():
    book = make_book(P1, JUNK)
    tr = narrate(P1)
    al = aligned(book, tr)
    assert states(al, ids_of(book, 1)) == {SKIPPED}


# ---------------------------------------------------------------- A4

def test_A4_palavras_comuns_casadas_por_acaso_sao_descartadas():
    # o narrador diz "and the" num trecho que no livro é propaganda
    book = make_book(P1, JUNK, P2)
    tr = narrate(P1, 1.0, "and the", 1.0, P2)
    al = aligned(book, tr)
    assert states(al, ids_of(book, 1)) == {SKIPPED}


# ---------------------------------------------------------------- A5

def test_A5_palavras_sem_par_dividem_o_tempo_proporcionalmente_as_letras():
    book = make_book(P1 + " xxxxxxxx yy " + P2)
    tr = narrate(P1, "qqq rrr", P2)
    al = aligned(book, tr)
    words = all_words(book)
    x = next(w for w in words if w["t"] == "xxxxxxxx")
    y = next(w for w in words if w["t"] == "yy")
    prev = words[words.index(x) - 1]
    nxt = words[words.index(y) + 1]
    t0, t1 = al.we[prev["id"]], al.ws[nxt["id"]]
    assert al.ws[x["id"]] == pytest.approx(t0)
    assert al.we[x["id"]] == pytest.approx(t0 + (t1 - t0) * 0.8)
    assert al.we[y["id"]] == pytest.approx(t1)


# ---------------------------------------------------------------- A6

def test_A6_tempos_nunca_diminuem_mesmo_se_o_narrador_repete_um_trecho():
    book = make_book(P1, P2, P3)
    tr = narrate(P1, P2, "there are actually only five things", P3)
    al = aligned(book, tr)
    times = [al.ws[w["id"]] for w in all_words(book) if al.state[w["id"]] == NARRATED]
    assert times == sorted(times)


def test_A6_repeticao_tardia_no_modo_incremental_nao_volta_no_tempo():
    # o narrador relê um trecho de P2 depois de P3; esse pedaço é localizado em P2
    book = make_book(P1, P2, P3)
    al = Aligner(book)
    al.add_segment(narrate(P1, P2, P3))
    al.add_segment(narrate(200.0, "there are actually only five things in any room"))
    al.compute()
    times = [al.ws[w["id"]] for w in all_words(book) if al.state[w["id"]] == NARRATED]
    assert times == sorted(times)


# ---------------------------------------------------------------- A7

def test_A7_texto_cujo_audio_nao_foi_transcrito_fica_pendente():
    book = make_book(P1, P2)
    tr = narrate(P1)                       # só o começo foi transcrito
    end = tr[-1]["e"]
    al = aligned(book, tr, covers=lambda a, b: b <= end + 0.5)
    assert states(al, ids_of(book, 0)) == {NARRATED}
    assert states(al, ids_of(book, 1)) == {PENDING}


def test_A7_buraco_na_transcricao_entre_dois_trechos_deixa_o_meio_pendente():
    book = make_book(P1, P2 + " " + P3)
    tr_a = narrate(P1)
    tr_c = narrate(60.0, P3)               # P3 começa em 60 s
    hole = (tr_a[-1]["e"] + 0.5, 59.0)     # 2º trecho não transcrito
    covers = lambda a, b: b <= hole[0] or a >= hole[1]
    al = aligned(book, tr_a + tr_c, covers)
    p2_ids = ids_of(book, 1)[:len(P2.split())]
    assert states(al, p2_ids) == {PENDING}
    assert states(al, ids_of(book, 0)) == {NARRATED}


# ---------------------------------------------------------------- A8

def test_A8_pedacos_incrementais_equivalem_ao_alinhamento_global():
    book = make_book(P1, JUNK, P2, P3)
    tr = narrate(P1, 2.0, P2, 1.0, P3)
    glob = aligned(book, tr)

    inc = Aligner(book)
    third = len(tr) // 3
    for piece in (tr[third:2 * third], tr[:third], tr[2 * third:]):   # fora de ordem
        inc.add_segment(piece)
    inc.compute()
    for w in all_words(book):
        k = w["id"]
        assert inc.state[k] == glob.state[k], w["t"]
        if glob.state[k] == NARRATED:
            assert inc.ws[k] == pytest.approx(glob.ws[k], abs=0.05)


def test_A8_pedaco_e_localizado_no_lugar_certo_do_livro():
    book = make_book(P1, P2, P3)
    piece = narrate(100.0, P3)
    al = Aligner(book)
    assert al.add_segment(piece)
    al.compute()
    assert states(al, ids_of(book, 2)) == {NARRATED}


# ---------------------------------------------------------------- A9

def test_A9_pedaco_sem_correspondencia_e_ignorado():
    book = make_book(P1, P2)
    al = Aligner(book)
    al.add_segment(narrate(P1))
    al.compute()
    before = list(al.ws)
    credits = narrate(50.0, "simon and schuster audio presents a production of something else entirely")
    assert al.add_segment(credits) is False
    al.compute()
    assert al.ws == before


def test_A9_pedaco_com_fragmento_coincidente_mas_quase_nada_casado_e_ignorado():
    book = make_book(P1, P2)
    al = Aligner(book)
    al.add_segment(narrate(P1))
    al.compute()
    before = list(al.ws)
    # só "five things in any" coincide com o livro; o resto é outra coisa
    other = narrate(80.0, "welcome back listeners five things in any order we discussed "
                          "yesterday on the podcast about gardening tools")
    assert al.add_segment(other) is False
    al.compute()
    assert al.ws == before


def test_A9_pedaco_metade_livro_metade_vinheta_e_aceito():
    book = make_book(P1, P2)
    al = Aligner(book)
    mixed = narrate(P2, "this has been a production of some audio company thank you for listening "
                        "to this audiobook please leave a review and see you next time goodbye")
    assert al.add_segment(mixed)
    al.compute()
    assert states(al, ids_of(book, 1)) == {NARRATED}


def test_A9_pedaco_com_metade_dos_tokens_casados_e_aceito():
    book = make_book(P1, P2)
    al = Aligner(book)
    # frases curtas do livro intercaladas com erros grosseiros: ~metade casa, sem 8 seguidos
    spoken = ("there are actually only qwe rty uio five things in any pas dfg room trash dishes "
              "hjk lzx laundry things that cvb nmq have a place")
    assert al.add_segment(narrate(spoken))


# ---------------------------------------------------------------- A10

def test_A10_pedaco_novo_substitui_casamentos_do_mesmo_intervalo():
    book = make_book(P1, P2)
    al = Aligner(book)
    al.add_segment(narrate(P1))
    # retranscrição do mesmo intervalo, com tempos um pouco diferentes
    redo = [{**w, "s": w["s"] + 0.05, "e": w["e"] + 0.05} for w in narrate(P1)]
    al.add_segment(redo)
    al.compute()
    first = all_words(book)[0]
    assert al.ws[first["id"]] == pytest.approx(0.05)
    assert len(al.match) == sum(len(w["n"]) for w in all_words(book)[:len(P1.split())])


def test_A10_casamento_antigo_que_nao_se_repete_na_retranscricao_some():
    book = make_book(P1, P2)
    words = all_words(book)
    target = next(w for w in words if w["t"] == "compassionate")
    tok = sum(len(w["n"]) for w in words[:words.index(target)])   # índice do token
    al = Aligner(book)
    al.add_segment(narrate(P1))
    assert tok in al.match
    al.add_segment(narrate(P1.replace("compassionate", "xyzzy")))
    assert tok not in al.match


# ---------------------------------------------------------------- A11

def test_A11_fala_fora_do_livro_nao_estica_as_palavras():
    book = make_book(P1 + " xxxx yyyy " + P2)
    digression = " ".join(["blah"] * 60)    # ~24 s de comentário do narrador
    tr = narrate(P1, digression, P2)
    al = aligned(book, tr)
    words = all_words(book)
    x = next(w for w in words if w["t"] == "xxxx")
    y = next(w for w in words if w["t"] == "yyyy")
    assert al.state[x["id"]] == NARRATED
    assert al.we[y["id"]] - al.ws[x["id"]] < 3.0


# ---------------------------------------------------------------- A12

COMMENT = "a woman wrote that she was proud of her messy house and then I got this comment:"
AFTER = "there it was the word that had haunted me for so much of my life as a messy woman"


def lazy_case(p=1.0):
    """O livro tem uma imagem onde a narradora lê 'lazy'."""
    book = make_book(COMMENT, "img:comentario.png", AFTER)
    tr = narrate(COMMENT, "lazy.", AFTER)
    for w in tr:
        if w["w"] == "lazy.":
            w["p"] = p
    return book, tr


def test_A12_palavra_lida_da_imagem_vira_texto_do_audio():
    book, tr = lazy_case()
    al = aligned(book, tr)
    assert len(al.extras) == 1
    extra = al.extras[0]
    assert [w["w"] for w in extra["words"]] == ["lazy."]
    comment = next(w for w in all_words(book) if w["t"] == "comment:")
    assert extra["after"] == comment["id"]
    lazy = next(w for w in tr if w["w"] == "lazy.")
    assert extra["words"][0]["s"] == pytest.approx(lazy["s"])


def test_A12_condicao_1_erros_dentro_do_texto_do_livro_nao_viram_texto_do_audio():
    book = make_book("by KC Davis " + P1)
    tr = narrate("by Casey Davis " + P1.replace("compassionate", "compassonite"))
    assert aligned(book, tr).extras == []


def test_A12_condicao_2_creditos_antes_e_material_depois_ficam_de_fora():
    book = make_book(P1)
    tr = narrate("simon and schuster audio presents", 1.0, P1, 1.0, "thank you for listening")
    assert aligned(book, tr).extras == []


def test_A12_condicao_3_trecho_pendente_nao_vira_texto_do_audio():
    book, tr = lazy_case()
    lazy = next(w for w in tr if w["w"] == "lazy.")
    # o áudio em volta de "lazy" ainda não foi transcrito por completo
    covers = lambda a, b: not (a < lazy["s"] < b)
    assert aligned(book, tr, covers).extras == []


@pytest.mark.parametrize("p", [0.45, 0.0])
def test_A12_condicao_4_palavra_com_baixa_confianca_nao_vira(p):
    book, tr = lazy_case(p=p)
    assert aligned(book, tr).extras == []


def test_A12_condicao_4_media_baixa_nao_vira():
    book = make_book(COMMENT, "img:x.png", AFTER)
    tr = narrate(COMMENT, "very lazy indeed", AFTER)
    for w in tr:
        if w["w"] in ("very", "lazy", "indeed"):
            w["p"] = 0.6                      # todas >= 0,5, mas a média fica abaixo de 0,7
    assert aligned(book, tr).extras == []


def test_A12_varios_trechos_cada_um_no_seu_lugar():
    book = make_book(P1, "img:a.png", P2, "img:b.png", P3)
    tr = narrate(P1, "first caption", P2, "second caption", P3)
    al = aligned(book, tr)
    assert [" ".join(w["w"] for w in e["words"]) for e in al.extras] == ["first caption", "second caption"]
    last_p1 = all_words(book)[len(P1.split()) - 1]
    assert al.extras[0]["after"] == last_p1["id"]


def test_A12_modo_incremental_tambem_detecta():
    book, tr = lazy_case()
    al = Aligner(book)
    al.add_segment(tr)
    al.compute()
    assert [w["w"] for e in al.extras for w in e["words"]] == ["lazy."]


def test_A12_condicao_5_palavra_acrescentada_no_meio_da_frase_fica_de_fora():
    book = make_book(P1, P2)
    # a narradora diz "the very messy" onde o livro diz "very messy"
    tr = narrate(P1.replace("a very messy", "a really very messy"), P2)
    assert aligned(book, tr).extras == []


def test_A12_condicao_5_trecho_entre_paragrafos_conta():
    book = make_book(P1, P2)
    tr = narrate(P1, "main point here", P2)
    assert [w["w"] for e in aligned(book, tr).extras for w in e["words"]] == ["main", "point", "here"]


def test_A12_condicao_6_nota_de_rodape_lida_fora_de_ordem_fica_de_fora():
    note = "executive functioning skills include focusing planning organizing and remembering"
    book = make_book(P1, P2, note, kinds=["p", "p", "note"])
    # a narradora lê a nota entre P1 e P2 (e não no lugar dela, no fim)
    tr = narrate(P1, note, P2)
    assert aligned(book, tr).extras == []


def test_A12_condicao_4_palavra_enfatizada_com_confianca_media_entra():
    book, tr = lazy_case(p=0.76)          # o "Lazy." real veio com 0,76
    assert [w["w"] for e in aligned(book, tr).extras for w in e["words"]] == ["lazy."]
