"""Pinned offline DTO token accounting; no model/provider calls or downloads.

The vendored o200k_base vocabulary and regex come from tiktoken 0.11.0
(MIT; see docs/data/TIKTOKEN_LICENSE). This is a named codec guarantee,
not a claim about other host tokenizers or repeated chat history.
The tiktoken package is not imported or required.
"""
from __future__ import annotations

import base64
from functools import lru_cache
import gzip
import hashlib
from importlib.resources import files
import heapq

import regex


class ProjectionEncoder:
    """Ordinary-text byte-pair encoder over the bundled, hash-checked vocabulary.

    Only the literal-text mode used for DTO accounting is supported: strings
    resembling special tokens remain source text. No native tokenizer or network
    cache is involved. Pair ties merge leftmost, as required by the rank table.
    """

    def __init__(self, pattern: str, ranks: dict[bytes, int]) -> None:
        self._pattern = regex.compile(pattern)
        self._ranks = ranks
        # Cache bounded pieces, not whole source documents or final payloads.
        self._cached_piece = lru_cache(maxsize=8192)(self._encode_piece)

    def _encode_piece(self, piece: bytes) -> tuple[int, ...]:
        direct = self._ranks.get(piece)
        if direct is not None:
            return (direct,)
        parts = [bytes((value,)) for value in piece]
        count = len(parts)
        previous = list(range(-1, count - 1))
        following = list(range(1, count)) + [-1]
        versions = [0] * count
        pairs: list[tuple[int, int, int]] = []

        def offer(left: int) -> None:
            if left < 0:
                return
            versions[left] += 1
            right = following[left]
            if right >= 0:
                rank = self._ranks.get(parts[left] + parts[right])
                if rank is not None:
                    heapq.heappush(pairs, (rank, left, versions[left]))

        for left in range(count - 1):
            offer(left)
        while pairs:
            _, left, version = heapq.heappop(pairs)
            if version != versions[left]:
                continue
            right = following[left]
            if right < 0:
                continue
            parts[left] += parts[right]
            parts[right] = b""
            versions[right] += 1
            following[left] = following[right]
            if following[right] >= 0:
                previous[following[right]] = left
            offer(previous[left])
            offer(left)
        return tuple(self._ranks[part] for part in parts if part)

    def encode(self, text: str, *, disallowed_special=()) -> list[int]:
        if disallowed_special:
            raise ValueError("projection encoder supports literal source text only")
        tokens: list[int] = []
        for match in self._pattern.finditer(text):
            piece = match.group().encode("utf-8")
            tokens.extend(
                self._cached_piece(piece) if len(piece) <= 1024 else self._encode_piece(piece)
            )
        return tokens


@lru_cache(maxsize=1)
def projection_encoder() -> ProjectionEncoder:

    data = gzip.decompress(files('docmancer.docs').joinpath('data/o200k_base.tiktoken.gz').read_bytes())
    if hashlib.sha256(data).hexdigest() != '446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d':
        raise ValueError('offline projection tokenizer vocabulary hash mismatch')
    ranks = {base64.b64decode(token): int(rank) for token, rank in (line.split() for line in data.splitlines())}
    pattern = '|'.join([
        r"[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]*[\p{Ll}\p{Lm}\p{Lo}\p{M}]+(?i:'s|'t|'re|'ve|'m|'ll|'d)?",
        r"[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]+[\p{Ll}\p{Lm}\p{Lo}\p{M}]*(?i:'s|'t|'re|'ve|'m|'ll|'d)?",
        r'\p{N}{1,3}', r' ?[^\s\p{L}\p{N}]+[\r\n/]*', r'\s*[\r\n]+', r'\s+(?!\S)', r'\s+',
    ])
    return ProjectionEncoder(pattern, ranks)


def projection_token_count(serialized: bytes) -> int:
    return len(projection_encoder().encode(serialized.decode('utf-8'), disallowed_special=()))
