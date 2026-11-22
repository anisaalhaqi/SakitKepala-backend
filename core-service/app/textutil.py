"""Utilitas teks murni (tanpa I/O) yang dipakai lintas konteks."""
from __future__ import annotations

import re

_WORD = re.compile(r"\w+", re.UNICODE)


def norm_topic(topic: str) -> str:
    """Kunci topic yang seragam: huruf kecil, spasi dirapikan, maks 80 karakter."""
    return re.sub(r"\s+", " ", topic.strip().lower())[:80]


def words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _shingles(ws: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(ws[i : i + n]) for i in range(len(ws) - n + 1)}


def copy_ratio(candidate: str, source: str, n: int = 5) -> float:
    """Porsi potongan n-kata milik `candidate` yang juga muncul persis di `source`.

    Linear terhadap panjang teks (cocok untuk CPU STB). Nilai dekat 1.0 berarti
    candidate hampir pasti salinan mentah dari source.
    """
    cand = _shingles(words(candidate), n)
    if not cand:
        return 0.0
    src = _shingles(words(source), n)
    return len(cand & src) / len(cand)
