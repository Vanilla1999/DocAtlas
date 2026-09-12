"""Pinned offline DTO token accounting; no model/provider calls or downloads.

The vendored o200k_base vocabulary and regex come from tiktoken 0.11.0
(MIT; see docs/data/TIKTOKEN_LICENSE). This is a named codec guarantee,
not a claim about other host tokenizers or repeated chat history.
"""
from __future__ import annotations

import base64
from functools import lru_cache
import gzip
import hashlib
from importlib.resources import files


@lru_cache(maxsize=1)
def projection_encoder():
    import tiktoken

    data = gzip.decompress(files('docmancer.docs').joinpath('data/o200k_base.tiktoken.gz').read_bytes())
    if hashlib.sha256(data).hexdigest() != '446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d':
        raise ValueError('offline projection tokenizer vocabulary hash mismatch')
    ranks = {base64.b64decode(token): int(rank) for token, rank in (line.split() for line in data.splitlines())}
    pattern = '|'.join([
        r"[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]*[\p{Ll}\p{Lm}\p{Lo}\p{M}]+(?i:'s|'t|'re|'ve|'m|'ll|'d)?",
        r"[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]+[\p{Ll}\p{Lm}\p{Lo}\p{M}]*(?i:'s|'t|'re|'ve|'m|'ll|'d)?",
        r'\p{N}{1,3}', r' ?[^\s\p{L}\p{N}]+[\r\n/]*', r'\s*[\r\n]+', r'\s+(?!\S)', r'\s+',
    ])
    return tiktoken.Encoding(name='docatlas_o200k_base', pat_str=pattern, mergeable_ranks=ranks,
                             special_tokens={'<|endoftext|>': 199999, '<|endofprompt|>': 200018})


def projection_token_count(serialized: bytes) -> int:
    return len(projection_encoder().encode(serialized.decode('utf-8'), disallowed_special=()))
