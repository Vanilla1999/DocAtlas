"""Dictionary-independent local experiment, not a product admission/proof engine.

Only query, source bytes and explicit scope metadata enter this module.
No fixture families, expected witnesses, aliases or topical labels are inputs.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter


def features(text, mode):
    words = re.findall(r"\w+", text.casefold(), flags=re.UNICODE)
    if mode == "lexical":
        return Counter(words)
    if mode != "char-tfidf":
        raise ValueError(mode)
    # General orthographic features, not a bilingual translation mechanism.
    return Counter(word[i:i + 3] for word in words for i in range(max(0, len(word) - 2)))


def eligibility(source, scope):
    meta, text = source["metadata"], source["text"]
    for field in ("project", "module", "version", "generation"):
        if meta.get(field) != scope.get(field):
            return False, field + "-mismatch"
    if meta.get("synchronized") is not True:
        return False, "unsynchronized"
    if hashlib.sha256(text.encode()).hexdigest() != meta.get("body_sha256"):
        return False, "hash-mismatch"
    if meta.get("offset_unit") != "unicode-code-point":
        return False, "unsupported-offset-unit"
    start, end = meta.get("start"), meta.get("end")
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
        return False, "invalid-range"
    return True, "eligible"


class Index:
    def __init__(self, sources, mode):
        self.sources = tuple(sources)
        self.mode = mode
        self.counts = [features(s["text"], mode) for s in sources]
        df = Counter(feature for counts in self.counts for feature in counts)
        self.idf = {f: math.log((1 + len(sources)) / (1 + n)) + 1 for f, n in df.items()}
        self.vectors = [self.vector(c) for c in self.counts]

    def vector(self, counts):
        values = {f: (1 + math.log(n)) * self.idf.get(f, 0) for f, n in counts.items()}
        norm = math.sqrt(sum(v * v for v in values.values()))
        return {f: v / norm for f, v in values.items()} if norm else {}

    def search(self, queries, scope, top_k, backend_available=True):
        if not queries or top_k < 1:
            raise ValueError("Need explicit queries and positive top_k")
        mode = self.mode if backend_available else "lexical"
        # Degraded exact/lexical path does not initialize another provider.
        degraded = Index(self.sources, "lexical") if mode != self.mode else self
        vectors = [degraded.vector(features(q, mode)) for q in queries]
        ranked = []
        for source, vec in zip(self.sources, degraded.vectors):
            scores = [sum(value * vec.get(f, 0) for f, value in q.items()) for q in vectors]
            score = max(scores)
            if score > 0:
                ranked.append(dict(source=source, score=score, query_scores=scores))
        ranked.sort(key=lambda r: (-r["score"], r["source"]["id"]))
        qualified, rejections = [], []
        for row in ranked:
            ok, reason = eligibility(row["source"], scope)
            if ok:
                qualified.append(row)
            else:
                rejections.append(dict(source_id=row["source"]["id"], reason=reason))
        return dict(retrieved=ranked, qualified=qualified, prefit=qualified[:top_k],
                    rejections=rejections, status="local-lexical-degraded" if not backend_available else "experimental-" + mode,
                    query_count=len(queries), extra_query_calls=0, network_calls=0, model_calls=0)


def project(rows, max_bytes):
    import json

    payload = dict(kind="experimental-context", sources=[], proof_status="not-evaluated")
    if len(json.dumps(payload, ensure_ascii=False).encode()) > max_bytes:
        raise ValueError("Empty DTO exceeds experimental byte budget")
    for row in rows:
        s = row["source"]
        m = s["metadata"]
        quote = dict(source_id=s["id"], source_sha256=m["body_sha256"],
                     start=m["start"], end=m["end"], text=s["text"][m["start"]:m["end"]])
        candidate = dict(payload, sources=payload["sources"] + [quote])
        if len(json.dumps(candidate, ensure_ascii=False).encode()) <= max_bytes:
            payload = candidate
    return payload
