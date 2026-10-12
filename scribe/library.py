"""Biblioteca: lembra os pares epub+áudio, a posição de leitura e onde fica o cache.

Tudo fica em ~/.local/share/scribe/ (ou $XDG_DATA_HOME/scribe):
  library.json          lista de livros e o último aberto
  books/<id>/           cache de cada livro (book.json, transcript/, images/…)
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import unicodedata
from pathlib import Path

AUDIO_EXT = {".m4b", ".m4a", ".mp3", ".ogg", ".opus", ".flac", ".wav", ".aac"}


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = Path(base) / "scribe"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fold(s: str) -> str:
    """Minúsculas, sem acentos, separadores viram espaço."""
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.replace("-", " ").replace("_", " ").split())


def book_id(epub_path: Path) -> str:
    h = hashlib.sha1()
    h.update(str(epub_path.stat().st_size).encode())
    with open(epub_path, "rb") as f:
        h.update(f.read(1 << 20))
    return h.hexdigest()[:16]


class Library:
    def __init__(self):
        self.path = data_dir() / "library.json"
        try:
            self.data = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            self.data = {"books": {}, "last": None, "ui": {}}
        self.data.setdefault("ui", {})

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1))
        tmp.rename(self.path)

    def cache(self, bid: str) -> Path:
        d = data_dir() / "books" / bid
        d.mkdir(parents=True, exist_ok=True)
        return d

    def resolve(self, paths: list[str]) -> tuple[str, dict]:
        """Interpreta os argumentos: arquivos e/ou pasta em qualquer ordem (L1), nada (L3)
        ou o nome/número de um livro registrado (L10)."""
        if not paths:
            bid = self.data.get("last")
            if not bid or bid not in self.data["books"]:
                raise SystemExit("Nenhum livro aberto ainda. Use: scribe play livro.epub audio.m4b")
            return bid, self._check_files(self.data["books"][bid])

        files: list[Path] = []
        names: list[str] = []
        for arg in paths:
            p = Path(arg).expanduser().resolve()
            if p.is_dir():
                files += sorted(x for x in p.iterdir() if x.is_file())
            elif p.exists():
                files.append(p)
            else:
                names.append(arg)
        if names:
            if files or len(names) > 1:
                raise SystemExit(f"Não encontrei o arquivo: {names[0]}")
            bid = self.find(names[0])
            return bid, self._check_files(self.data["books"][bid])

        epubs = [f for f in files if f.suffix.lower() == ".epub"]
        audios = [f for f in files if f.suffix.lower() in AUDIO_EXT]
        if len(epubs) != 1:
            raise SystemExit("Preciso de exatamente um .epub.")
        epub = epubs[0]
        bid = book_id(epub)
        entry = self.data["books"].get(bid, {})
        entry["epub"] = str(epub)
        if audios:
            if len(audios) > 1:
                raise SystemExit("Por enquanto só um arquivo de áudio por livro (ex.: .m4b).")
            entry["audio"] = str(audios[0])
        if not entry.get("audio") or not Path(entry["audio"]).exists():
            raise SystemExit("Qual é o áudio desse livro? scribe play livro.epub audio.m4b")
        entry.setdefault("position", 0.0)
        self.data["books"][bid] = entry
        self._migrate_sibling_cache(epub, bid)
        self.save()
        return bid, entry

    def _check_files(self, entry: dict) -> dict:
        """L10: avisa se um arquivo registrado sumiu."""
        for key, what in (("epub", "O EPUB"), ("audio", "O áudio")):
            path = entry.get(key)
            if not path or not Path(path).exists():
                raise SystemExit(
                    f"{what} registrado não existe mais: {path}\n"
                    f"Se ele mudou de lugar, registre de novo: "
                    f"scribe play caminho/do/livro.epub caminho/do/audio")
        return entry

    def books(self) -> list[dict]:
        """L9: livros registrados, do aberto mais recentemente para o mais antigo."""
        items = sorted(self.data["books"].items(), key=lambda kv: kv[1].get("opened", 0),
                       reverse=True)
        return [{"num": n, "bid": bid, "title": e.get("title") or Path(e["epub"]).stem,
                 "position": e.get("position", 0.0), "epub": e["epub"],
                 "audio": e.get("audio"), "last": bid == self.data.get("last")}
                for n, (bid, e) in enumerate(items, start=1)]

    def find(self, name: str) -> str:
        """L10: livro registrado pelo número, nome do arquivo ou trecho do título."""
        rows = self.books()
        if name.strip().isdigit():
            for r in rows:
                if r["num"] == int(name):
                    return r["bid"]
            raise SystemExit(f"Não há livro número {name}. Veja: scribe list")
        key = _fold(name.removesuffix(".epub").removesuffix(".EPUB"))
        exact = [r for r in rows if _fold(Path(r["epub"]).stem) == key]
        if len(exact) == 1:
            return exact[0]["bid"]
        partial = [r for r in rows
                   if key in _fold(Path(r["epub"]).stem) or key in _fold(r["title"])]
        if len(partial) == 1:
            return partial[0]["bid"]
        if not partial:
            raise SystemExit(f"Não encontrei \"{name}\" (nem como arquivo, nem entre os livros "
                             f"registrados). Veja: scribe list")
        options = "\n".join(f"  {r['num']:>2}  {r['title']}" for r in partial)
        raise SystemExit(f"\"{name}\" serve para mais de um livro:\n{options}\n"
                         f"Use um nome mais específico ou o número.")

    def _migrate_sibling_cache(self, epub: Path, bid: str):
        """Aproveita um cache antigo `<livro>.scribe/` ao lado do epub."""
        old = epub.with_name(epub.stem + ".scribe")
        new = data_dir() / "books" / bid
        if old.is_dir() and not (new / "transcript").exists():
            new.parent.mkdir(parents=True, exist_ok=True)
            if new.exists():
                new.rmdir() if not any(new.iterdir()) else None
            if not new.exists():
                old.rename(new)

    def touch(self, bid: str, **fields):
        e = self.data["books"][bid]
        e.update(fields)
        e["opened"] = time.time()
        self.data["last"] = bid
        self.save()

    def set_position(self, bid: str, pos: float):
        self.data["books"][bid]["position"] = round(pos, 2)
        self.save()
