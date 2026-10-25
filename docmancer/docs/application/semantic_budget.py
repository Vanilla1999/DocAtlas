"""Request-owned limits shared by every forward pass of a local checker."""
from __future__ import annotations
from dataclasses import dataclass, field
import time


class Exhausted(RuntimeError):
    pass


@dataclass
class Budget:
    seconds: float
    max_pairs: int
    started: float = field(default_factory=time.monotonic)
    pairs: int = 0
    pair_tokens: int = 0
    cache_hits: int = 0

    def check(self):
        if time.monotonic() - self.started >= self.seconds or self.pairs >= self.max_pairs:
            raise Exhausted("request_budget_exhausted")

    def take(self, tokens):
        self.check()
        self.pairs += 1
        self.pair_tokens += tokens

    def elapsed(self):
        return time.monotonic() - self.started


class CachedQA:
    """Reuse identical contiguous windows, never substitute a different context.

    The original reader's model/decoder and source-coordinate definition are
    retained. Unlike independent reader.assess calls, every actual ONNX forward
    belongs to one request budget. Partial results never masquerade as complete.
    """
    def __init__(self, reader, budget):
        self.reader, self.budget, self.cache = reader, budget, {}

    def assess(self, question, contexts):
        import numpy as np
        from . import answerability as qa
        reader, budget = self.reader, self.budget
        query = reader.tokenizer.encode(question, add_special_tokens=False).ids
        if not 0 < len(query) <= qa.MAX_QUERY_TOKENS:
            raise qa.AnswerabilityError("answerability_query_limit")
        width = qa.MAX_SEQUENCE - len(query) - 4
        best, candidate = -float("inf"), None
        for context in contexts:
            key = (question, context["identity_sha256"], context["char_start"], context["text"])
            if key in self.cache:
                budget.cache_hits += 1
                margin, span = self.cache[key]
            else:
                enc = reader.tokenizer.encode(context["text"], add_special_tokens=False)
                if not enc.ids:
                    raise qa.AnswerabilityError("answerability_empty_tokenization")
                margin, span = -float("inf"), None
                for offset in range(0, len(enc.ids), width - qa.OVERLAP):
                    part = enc.ids[offset:offset + width]
                    ids = [reader.bos] + query + [reader.eos, reader.eos] + part + [reader.eos]
                    budget.take(len(ids))
                    feeds = {"input_ids": np.asarray([ids], dtype=np.int64),
                             "attention_mask": np.ones((1, len(ids)), dtype=np.int64)}
                    outputs = reader.session.run(None, {k: v for k, v in feeds.items() if k in reader.names})
                    if budget.elapsed() >= budget.seconds:
                        raise Exhausted("request_deadline")
                    if len(outputs) != 2:
                        raise qa.AnswerabilityError("answerability_model_contract")
                    start, end = (np.asarray(a).reshape(-1) for a in outputs)
                    if len(start) != len(ids) or len(end) != len(ids) or not np.isfinite(start).all() or not np.isfinite(end).all():
                        raise qa.AnswerabilityError("answerability_invalid_logits")
                    null = float(start[0] + end[0]); base = len(query) + 3
                    for i in range(len(part)):
                        j = i + int(np.argmax(end[base+i:base+min(len(part), i+qa.MAX_ANSWER_TOKENS)]))
                        value = float(start[base+i] + end[base+j]) - null
                        if value > margin:
                            margin = value
                            span = (enc.offsets[offset+i][0], enc.offsets[offset+j][1])
                    if offset + width >= len(enc.ids):
                        break
                self.cache[key] = (margin, span)
            if margin > best:
                best = margin
                candidate = {"source_ids": list(context["ids"]), "identity_sha256": context["identity_sha256"],
                             "char_start": context["char_start"] + span[0],
                             "char_end": context["char_start"] + span[1]}
        if candidate is None:
            raise qa.AnswerabilityError("answerability_empty_inputs")
        return {"decision": "candidate_answer" if best >= 0 else "no_answer",
                "candidate": candidate, "best_span_minus_null": best}
