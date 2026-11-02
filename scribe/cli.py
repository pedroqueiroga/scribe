"""Linha de comando: scribe play | list | prepare | check."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _open(paths: list[str]):
    """Resolve os argumentos na biblioteca e carrega o livro (extraindo, se preciso)."""
    from .library import Library
    from .session import load_book
    lib = Library()
    bid, entry = lib.resolve(paths)
    cache = lib.cache(bid)
    book = load_book(entry["epub"], cache)
    lib.touch(bid, title=book["title"])
    return lib, bid, entry, cache, book


def _transcribe_all(entry: dict, cache: Path, language: str, model_size: str):
    """Transcreve o livro inteiro sem interface (mesmo laço do streaming)."""
    from . import audio, worker
    from .store import TranscriptStore
    store = TranscriptStore(cache)
    duration = float(audio.probe(entry["audio"])["format"]["duration"])
    whisper = worker.make_whisper(entry["audio"], language, model_size)

    def report(msg):
        if msg["type"] == "segment":
            done = sum(b - a for a, b in store.intervals)
            print(f"\r[sincronizando] {done / duration:6.1%}", end="", file=sys.stderr, flush=True)

    worker.transcribe_loop(store, duration, lambda: [], whisper, report)
    print(file=sys.stderr)


def _align_all(cache: Path):
    from . import align
    align.run(cache)


def cmd_prepare(args):
    lib, bid, entry, cache, book = _open(args.paths)
    _transcribe_all(entry, cache, book["language"], args.model)
    _align_all(cache)


def cmd_list(args):
    from .library import Library
    rows = Library().books()
    if not rows:
        print("A biblioteca está vazia. Comece com: scribe play texto.epub audio.m4b")
        return
    for r in rows:
        t = int(r["position"])
        pos = f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"
        mark = "*" if r["last"] else " "
        print(f"{mark} {r['num']:>2}  {r['title'][:50]:50s}  {pos:>8s}  {r['epub']}")


def cmd_check(args):
    from . import align
    from .library import Library
    lib = Library()
    bid, _ = lib.resolve(args.paths)
    align.run(lib.cache(bid))
    align.report(lib.cache(bid), verbose=args.verbose)


def cmd_play(args):
    from . import overlay
    overlay.main(args.paths, args.model, oneline=args.oneline, full=args.full)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="scribe", description="áudio e texto sincronizados, palavra por palavra")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("play", help="abre um texto com o áudio (arquivos, pasta, nome ou número)")
    pl.add_argument("paths", nargs="*", help="texto.epub audio.m4b | pasta | nome | número")
    pl.add_argument("--model", default="small", help="precisão da sincronia: small (padrão) ou medium, mais lento")
    pl.add_argument("--oneline", action="store_true",
                    help="abre no modo de uma linha (janela baixa, só a linha falada)")
    pl.add_argument("--full", action="store_true",
                    help="abre no modo completo (o texto inteiro, como num leitor de e-book)")
    pl.set_defaults(func=cmd_play)

    ls = sub.add_parser("list", help="mostra a biblioteca")
    ls.set_defaults(func=cmd_list)

    p = sub.add_parser("prepare", help="sincroniza o áudio inteiro de antemão, sem janela")
    p.add_argument("paths", nargs="*")
    p.add_argument("--model", default="small")
    p.set_defaults(func=cmd_prepare)

    c = sub.add_parser("check", help="mostra como o texto e o áudio estão batendo")
    c.add_argument("paths", nargs="*")
    c.add_argument("-v", "--verbose", action="store_true")
    c.set_defaults(func=cmd_check)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
