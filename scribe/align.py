"""Alinhamento texto do EPUB <-> transcrição, gerando sync.json.

1. Ambos os lados viram sequências de tokens normalizados.
2. Âncoras: n-gramas que aparecem uma única vez em cada lado; a maior
   subsequência crescente delas fixa pontos de casamento. O processo é
   recursivo nos trechos entre âncoras, com n-gramas cada vez menores.
3. Trechos pequenos: Needleman-Wunsch com similaridade fuzzy.
4. Palavras do livro sem par recebem tempo interpolado (proporcional ao
   número de letras) ou são marcadas como não narradas.
"""
from __future__ import annotations

import bisect
import json
import sys
from collections import Counter
from pathlib import Path

from rapidfuzz.distance import Levenshtein

from . import epub as epubmod


DP_LIMIT = 300_000          # células máximas para o DP direto
NGRAM_SIZES = (10, 6, 4, 3, 2, 1)
WORDS_PER_SEC = 2.6         # ritmo típico de narração
MIN_WORD_DUR = 0.08


# ---------------------------------------------------------------- matching

def _similar(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if min(len(a), len(b)) < 3:
        return 0.0
    return Levenshtein.normalized_similarity(a, b)


def _lis(pairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Maior subsequência estritamente crescente em j (pairs ordenados por i)."""
    tails: list[int] = []
    tails_idx: list[int] = []
    prev = [-1] * len(pairs)
    for k, (_, j) in enumerate(pairs):
        pos = bisect.bisect_left(tails, j)
        if pos == len(tails):
            tails.append(j)
            tails_idx.append(k)
        else:
            tails[pos] = j
            tails_idx[pos] = k
        prev[k] = tails_idx[pos - 1] if pos > 0 else -1
    out = []
    k = tails_idx[-1] if tails_idx else -1
    while k >= 0:
        out.append(pairs[k])
        k = prev[k]
    return out[::-1]


def _unique_ngrams(seq: list[str], lo: int, hi: int, n: int) -> dict[tuple, int]:
    counts: Counter = Counter()
    first: dict[tuple, int] = {}
    for i in range(lo, hi - n + 1):
        g = tuple(seq[i:i + n])
        counts[g] += 1
        first.setdefault(g, i)
    return {g: first[g] for g, c in counts.items() if c == 1}


def _dp(a, alo, ahi, b, blo, bhi, out):
    """Needleman-Wunsch local ao trecho; adiciona pares casados em `out`."""
    n, m = ahi - alo, bhi - blo
    if n == 0 or m == 0:
        return
    GAP = -0.6
    # score[i][j]; trilha em matriz de bytes
    prev = [j * GAP for j in range(m + 1)]
    trace = [bytearray(m + 1) for _ in range(n + 1)]
    for j in range(1, m + 1):
        trace[0][j] = 2
    for i in range(1, n + 1):
        cur = [i * GAP] + [0.0] * m
        tr = trace[i]
        tr[0] = 1
        ai = a[alo + i - 1]
        for j in range(1, m + 1):
            s = _similar(ai, b[blo + j - 1])
            diag = prev[j - 1] + (2.0 if s == 1.0 else (s * 2 - 0.8 if s >= 0.75 else -1.0))
            up = prev[j] + GAP
            left = cur[j - 1] + GAP
            if diag >= up and diag >= left:
                cur[j] = diag
                tr[j] = 0
            elif up >= left:
                cur[j] = up
                tr[j] = 1
            else:
                cur[j] = left
                tr[j] = 2
        prev = cur
    i, j = n, m
    pairs = []
    while i > 0 or j > 0:
        t = trace[i][j]
        if i > 0 and j > 0 and t == 0:
            if _similar(a[alo + i - 1], b[blo + j - 1]) >= 0.75:
                pairs.append((alo + i - 1, blo + j - 1))
            i -= 1
            j -= 1
        elif i > 0 and (t == 1 or j == 0):
            i -= 1
        else:
            j -= 1
    out.extend(reversed(pairs))


def _align(a, alo, ahi, b, blo, bhi, out, level=0):
    n, m = ahi - alo, bhi - blo
    if n == 0 or m == 0:
        return
    if n * m <= DP_LIMIT:
        _dp(a, alo, ahi, b, blo, bhi, out)
        return
    for size in NGRAM_SIZES[level:]:
        ua = _unique_ngrams(a, alo, ahi, size)
        ub = _unique_ngrams(b, blo, bhi, size)
        pairs = sorted((i, ub[g]) for g, i in ua.items() if g in ub)
        if not pairs:
            continue
        chain = _lis(pairs)
        # âncoras não sobrepostas
        anchors = []
        ei = ej = -1
        for i, j in chain:
            if i >= ei and j >= ej:
                anchors.append((i, j))
                ei, ej = i + size, j + size
        if not anchors:
            continue
        nxt = NGRAM_SIZES.index(size)
        ci, cj = alo, blo
        for i, j in anchors:
            _align(a, ci, i, b, cj, j, out, nxt)
            out.extend((i + k, j + k) for k in range(size))
            ci, cj = i + size, j + size
        _align(a, ci, ahi, b, cj, bhi, out, nxt)
        return
    # nenhuma âncora: trechos sem relação (ex.: texto não narrado)
    if min(n, m) * 4 >= max(n, m) and n * m <= DP_LIMIT * 8:
        _dp(a, alo, ahi, b, blo, bhi, out)



# ---------------------------------------------------------------- motor

PENDING, NARRATED, SKIPPED = 0, 1, 2   # estado de cada palavra do livro


def _transcript_tokens(words: list[dict], lang: str):
    tokens, times = [], []
    for w in words:
        norm = epubmod.normalize(w["w"], lang)
        if not norm:
            continue
        dur = (w["e"] - w["s"]) / len(norm)
        for k, t in enumerate(norm):
            tokens.append(t)
            times.append((w["s"] + k * dur, w["s"] + (k + 1) * dur))
    return tokens, times


MIN_MATCHED_FRACTION = 0.5   # A9
MIN_MATCHED_RUN = 8          # A9


def _enough_overlap(pairs: list[tuple[int, int]], n_tokens: int) -> bool:
    """A9: metade dos tokens casados, ou uma sequência de 8 casados seguidos."""
    if len(pairs) >= n_tokens * MIN_MATCHED_FRACTION:
        return True
    run = best = 0
    prev = None
    for i, j in pairs:
        run = run + 1 if prev and i == prev[0] + 1 and j == prev[1] + 1 else 1
        best = max(best, run)
        prev = (i, j)
    return best >= MIN_MATCHED_RUN


class Aligner:
    """Mantém o casamento livro<->áudio e produz os tempos de cada palavra.

    `align_all` faz o alinhamento global de tudo que já foi transcrito;
    `add_segment` encaixa um pedaço novo localmente (rápido, para streaming).
    """

    def __init__(self, book: dict):
        self.lang = book["language"]
        self.tokens: list[str] = []
        self.owner: list[int] = []
        self.words: list[dict] = []
        self.blocks: list[dict] = []
        for ch in book["chapters"]:
            for b in ch["blocks"]:
                b["chapter"] = ch["index"]
                self.blocks.append(b)
                for w in b["words"]:
                    w["block"] = b["id"]
                    self.words.append(w)
                    for t in w["n"]:
                        self.tokens.append(t)
                        self.owner.append(w["id"])
        self.match: dict[int, tuple[float, float]] = {}  # token do livro -> tempo
        self.tstarts: list[float] = []  # início de cada palavra transcrita (ordenado)
        self.twords: list[dict] = []    # palavras transcritas, ordenadas por início
        self.extras: list[dict] = []    # A12: trechos só do áudio
        self._tri: dict[tuple, list[int]] = {}
        for i in range(len(self.tokens) - 2):
            self._tri.setdefault(tuple(self.tokens[i:i + 3]), []).append(i)
        # resultado de compute()
        self.ws = [None] * len(self.words)
        self.we = [None] * len(self.words)
        self.state = [PENDING] * len(self.words)

    # -- casamento

    def align_all(self, transcript_words: list[dict]):
        ttok, times = _transcript_tokens(transcript_words, self.lang)
        pairs: list[tuple[int, int]] = []
        _align(self.tokens, 0, len(self.tokens), ttok, 0, len(ttok), pairs)
        self.match = {i: times[j] for i, j in pairs}
        self.twords = sorted(transcript_words, key=lambda w: w["s"])
        self.tstarts = [w["s"] for w in self.twords]

    def locate(self, ttok: list[str]) -> tuple[int, int] | None:
        """Janela provável do livro para uma sequência de tokens transcritos."""
        votes: Counter = Counter()
        for j in range(len(ttok) - 2):
            pos = self._tri.get(tuple(ttok[j:j + 3]))
            if not pos or len(pos) > 12:
                continue
            for i in pos:
                votes[(i - j) // 40] += 1
        if not votes:
            return None
        best, score = max(((b, votes[b - 1] + votes[b] + votes[b + 1]) for b in votes),
                          key=lambda x: x[1])
        if score < max(2, (len(ttok) - 2) * 0.08):
            return None
        start = best * 40
        lo = max(0, start - 80)
        hi = min(len(self.tokens), start + int(len(ttok) * 1.4) + 120)
        return lo, hi

    def add_segment(self, seg_words: list[dict]) -> bool:
        ttok, times = _transcript_tokens(seg_words, self.lang)
        if len(ttok) < 3:
            return False
        win = self.locate(ttok)
        if win is None:
            return False
        lo, hi = win
        pairs: list[tuple[int, int]] = []
        _align(self.tokens, lo, hi, ttok, 0, len(ttok), pairs)
        if not _enough_overlap(pairs, len(ttok)):
            return False
        t_lo, t_hi = times[0][0], times[-1][1]
        # remove casamentos antigos que caem no mesmo intervalo de áudio
        for i in [i for i, (s, _) in self.match.items() if t_lo <= s <= t_hi]:
            del self.match[i]
        for i, j in pairs:
            self.match[i] = times[j]
        # palavras transcritas: as do mesmo intervalo são substituídas pelas novas
        self.twords = sorted([w for w in self.twords if not (t_lo <= w["s"] <= t_hi)] + list(seg_words),
                             key=lambda w: w["s"])
        self.tstarts = [w["s"] for w in self.twords]
        return True

    def _spoken(self, t0: float, t1: float) -> int:
        """Quantas palavras transcritas começam estritamente entre t0 e t1."""
        return bisect.bisect_left(self.tstarts, t1 - 0.02) - bisect.bisect_right(self.tstarts, t0 + 0.02)

    # -- tempos

    def _clustered_matches(self, min_size: int = 3, max_gap: int = 3, max_dt: float = 3.0):
        """Casamentos agrupados; grupos pequenos (palavras soltas casadas por acaso
        dentro de texto não narrado) são descartados."""
        items = sorted(self.match.items())
        out, cluster = [], []
        for i, (s, e) in items:
            if cluster:
                pi, (ps, pe) = cluster[-1]
                if i - pi > max_gap or s - pe > max_dt or s < ps:
                    if len(cluster) >= min_size:
                        out.extend(cluster)
                    cluster = []
            cluster.append((i, (s, e)))
        if len(cluster) >= min_size:
            out.extend(cluster)
        return out


    def compute(self, covers=lambda a, b: True):
        """Calcula início/fim de cada palavra. `covers(a, b)` diz se o áudio
        entre a e b já foi transcrito (senão a lacuna fica pendente)."""
        n = len(self.words)
        ws: list = [None] * n
        we: list = [None] * n
        m = [0] * n
        for i, (s, e) in self._clustered_matches():
            k = self.owner[i]
            ws[k] = s if ws[k] is None else min(ws[k], s)
            we[k] = e if we[k] is None else max(we[k], e)
            m[k] += 1

        # monotonicidade: palavras fora de ordem viram lacuna
        last = -1.0
        for k in range(n):
            if ws[k] is None:
                continue
            if ws[k] < last:
                ws[k] = we[k] = None
                m[k] = 0
                continue
            if we[k] < ws[k] + MIN_WORD_DUR:
                we[k] = ws[k] + MIN_WORD_DUR
            last = ws[k]

        state = [NARRATED if ws[k] is not None else PENDING for k in range(n)]
        anchored = [k for k in range(n) if ws[k] is not None]
        if not anchored:
            self.ws, self.we, self.state, self.matched = ws, we, state, m
            return
        spans = [(-1, anchored[0])] + list(zip(anchored, anchored[1:])) + [(anchored[-1], n)]
        for a, b in spans:
            if b - a <= 1:
                continue
            gap = range(a + 1, b)
            cnt = len(gap)
            expected = cnt / WORDS_PER_SEC
            t0 = we[a] if a >= 0 else None
            t1 = ws[b] if b < n else None
            if t0 is None or t1 is None:
                edge_known = covers(0.0, t1) if t0 is None else covers(t0, t0 + expected + 1)
                if not edge_known:
                    continue  # pendente
                if cnt > 8:
                    for k in gap:
                        state[k] = SKIPPED
                    continue
                t0 = max(0.0, t1 - expected) if t0 is None else t0
                t1 = t0 + expected
            else:
                if not covers(t0, t1):
                    continue  # pendente: buraco na transcrição
                # o narrador falou bem menos palavras do que o livro tem aqui?
                if cnt > 3 and self._spoken(t0, t1) < cnt * 0.35:
                    for k in gap:
                        state[k] = SKIPPED
                    continue
            span = t1 - t0
            if span > expected * 3 + 2:  # narrador falou algo fora do livro
                span = expected * 1.2
            lens = [max(1, len(self.words[k]["t"])) for k in gap]
            total = sum(lens)
            acc = 0
            for k, L in zip(gap, lens):
                ws[k] = t0 + span * acc / total
                acc += L
                we[k] = t0 + span * acc / total
                state[k] = NARRATED
        self.ws, self.we, self.state, self.matched = ws, we, state, m
        self.extras = self._audio_only(covers)

    def _audio_only(self, covers) -> list[dict]:
        """A12: trechos falados que não existem no livro, com confiança alta."""
        nar = [k for k in range(len(self.words)) if self.state[k] == NARRATED]
        if not nar:
            return []
        starts = [self.ws[k] for k in nar]
        eps = 0.02

        def overlaps_book(w):                                   # condição 1
            i = bisect.bisect_left(starts, w["e"] - eps)
            for j in (i - 1, i - 2):
                if 0 <= j < len(nar) and self.we[nar[j]] > w["s"] + eps and starts[j] < w["e"] - eps:
                    return True
            return False

        groups: list[list[dict]] = []
        current: list[dict] = []
        for w in self.twords:
            if overlaps_book(w):
                if current:
                    groups.append(current)
                current = []
            else:
                current.append(w)
        if current:
            groups.append(current)

        out = []
        for g in groups:
            t0, t1 = g[0]["s"], g[-1]["e"]
            i = bisect.bisect_right(starts, t0) - 1
            if i < 0 or i + 1 >= len(nar):                      # condição 2
                continue
            prev, nxt = nar[i], nar[i + 1]
            if self.we[prev] > t0 + eps or self.ws[nxt] < t1 - eps:
                continue
            if not covers(self.we[prev], self.ws[nxt]):         # condição 3 (áudio)
                continue
            if any(self.state[k] == PENDING for k in range(prev + 1, nxt)):   # condição 3
                continue
            ps = [w.get("p", 1.0) for w in g]
            if min(ps) < 0.5 or sum(ps) / len(ps) < 0.7:        # condição 4
                continue
            if not self._at_break(prev, nxt):                   # condição 5
                continue
            if self._in_book_nearby(g, prev):                   # condição 6
                continue
            out.append({"after": self.words[prev]["id"],
                        "words": [{"w": w["w"], "s": w["s"], "e": w["e"]} for w in g]})
        return out

    def _at_break(self, prev: int, nxt: int) -> bool:
        """A12.5: imagem entre as duas palavras, ou parágrafos diferentes."""
        b0, b1 = self.words[prev]["block"], self.words[nxt]["block"]
        if b0 != b1:
            return True
        return False

    def _in_book_nearby(self, group: list[dict], prev: int, reach: int = 2000) -> bool:
        """A12.6: a maioria dos trigramas do trecho existe no livro por perto."""
        toks = [t for w in group for t in epubmod.normalize(w["w"], self.lang)]
        if len(toks) < 3:
            return False
        try:
            center = self.owner.index(self.words[prev]["id"])
        except ValueError:
            return False
        lo, hi = center - reach, center + reach
        grams = [tuple(toks[i:i + 3]) for i in range(len(toks) - 2)]
        found = sum(1 for g in grams if any(lo <= i <= hi for i in self._tri.get(g, ())))
        return found * 2 > len(grams)

    # -- saída

    def to_sync(self, book: dict, audio_chapters: list[dict]) -> dict:
        out_blocks = []
        last_end = 0.0
        narrated_chapters = set()
        for b in self.blocks:
            ids = [w["id"] for w in b["words"]]
            nar = [k for k in ids if self.state[k] == NARRATED]
            if b["kind"] == "img":
                s, e, st = last_end, None, NARRATED
            elif nar:
                s, e, st = self.ws[nar[0]], self.we[nar[-1]], NARRATED
                last_end = e
                narrated_chapters.add(b["chapter"])
            else:
                s = e = None
                st = SKIPPED if ids and all(self.state[k] == SKIPPED for k in ids) else PENDING
            out_blocks.append({
                "id": b["id"], "chapter": b["chapter"], "kind": b["kind"], "state": st,
                "s": _r(s), "e": _r(e),
                **({"src": b["src"], "alt": b.get("alt", "")} if b["kind"] == "img" else {}),
                "words": [[w["t"], _r(self.ws[w["id"]]), _r(self.we[w["id"]]),
                           self.state[w["id"]], 1 if self.matched[w["id"]] else 0]
                          for w in b["words"]],
            })
        for b in out_blocks:
            if b["kind"] == "img" and not ({b["chapter"], b["chapter"] - 1} & narrated_chapters):
                b["state"] = SKIPPED
        return {
            "title": book["title"],
            "language": book["language"],
            "chapters": [{"index": c["index"], "title": c["title"]} for c in book["chapters"]],
            "audio_chapters": audio_chapters,
            "blocks": out_blocks,
        }


def _r(x):
    return None if x is None else round(x, 3)


def run(cache: Path, audio_path: str | None = None) -> dict:
    """Alinhamento global de tudo que já foi transcrito -> sync.json."""
    from .store import TranscriptStore
    book = json.loads((cache / "book.json").read_text())
    store = TranscriptStore(cache)
    if not store.segments:
        sys.exit("Sem transcrição ainda.")
    al = Aligner(book)
    al.align_all(store.words())
    al.compute(store.covers)
    chapters_path = cache / "audio_chapters.json"
    achs = json.loads(chapters_path.read_text()) if chapters_path.exists() else []
    sync = al.to_sync(book, achs)
    (cache / "sync.json").write_text(json.dumps(sync, ensure_ascii=False))
    report(cache)
    return sync


# ---------------------------------------------------------------- relatório

def report(cache: Path, verbose: bool = False):
    sync = json.loads((cache / "sync.json").read_text())
    titles = {c["index"]: c["title"] for c in sync["chapters"]}
    per: dict[int, list] = {}
    for b in sync["blocks"]:
        if b["kind"] == "img":
            continue
        st = per.setdefault(b["chapter"], [0, 0, 0, 0, None, None])
        for t, s, e, state, m in b["words"]:
            st[0] += 1
            if state == NARRATED:
                st[1] += 1
                st[2] += m
                st[4] = s if st[4] is None else min(st[4], s)
                st[5] = e if st[5] is None else max(st[5], e)
            elif state == PENDING:
                st[3] += 1
    tot = [0, 0, 0, 0]
    print(f"{'seção':40s} {'palavras':>8s} {'narradas':>8s} {'casadas':>8s} {'pendentes':>9s}  tempo")
    for ch, (n, nar, mat, pen, s, e) in sorted(per.items()):
        for k, v in enumerate((n, nar, mat, pen)):
            tot[k] += v
        span = f"{_fmt(s)}–{_fmt(e)}" if s is not None else "—"
        pct = f"{mat / nar:7.1%}" if nar else "      —"
        print(f"{titles[ch][:40]:40s} {n:8d} {nar:8d} {pct:>8s} {pen:9d}  {span}")
    print(f"{'TOTAL':40s} {tot[0]:8d} {tot[1]:8d} {tot[2] / max(1, tot[1]):7.1%} {tot[3]:9d}")
    if verbose:
        print("\nTrechos interpolados longos (possíveis problemas):")
        run_words, run_start = [], None
        for b in sync["blocks"]:
            for t, s, e, state, m in b["words"]:
                if state == NARRATED and not m:
                    if not run_words:
                        run_start = s
                    run_words.append(t)
                else:
                    if len(run_words) >= 15:
                        print(f"  {_fmt(run_start)}  {' '.join(run_words)[:120]}")
                    run_words = []


def _fmt(t):
    if t is None:
        return "—"
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"
