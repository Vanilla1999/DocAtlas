"""Experimental retrieval relevance only; trusted bindings are not answer proof."""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import re
from unittest.mock import patch
import section_scope
from section_scope import ScopeBinder, present, explicit_owners
from docmancer.docs.domain.evidence_qualification import _visible_term_present

BASE_LABEL = section_scope.label
MODES = {"catalog": (True, False, False), "spelling": (False, True, False),
         "one_anchor": (False, False, True), "combined": (True, True, True)}


def heading_words(text):
    return tuple(re.findall(r"[A-Za-z]+", text.casefold()))


def camel_words(name):
    if not re.fullmatch(r"[A-Za-z]+", name) or not re.search(r"[a-z][A-Z]", name):
        return ()
    return tuple(w.casefold() for w in re.findall(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+", name))


def explicit_identity(question, name):
    """Do not relax spelling for code references or requested API identity."""
    n = re.escape(name)
    return bool(re.search(r"\b(?:signature|constructor|class|identifier|import)\b|сигнатур|конструктор|\bкласс|идентификатор", question, re.I)
                or re.search(rf"`[^`]*\b{n}\b[^`]*`|\b{n}\s*\(|[\w.]\.{n}\b|\b{n}\.", question, re.I))


def definition_anchor(term, snippet, proof):
    if heading_words(proof['headings'][-1]['text']) != (term.casefold(),):
        return False
    if len(re.findall(r"[A-Za-z]+", snippet)) < 6:
        return False
    return bool(re.search(rf"(?:^|\n)\s*(?:An?\s+|The\s+)?`?{re.escape(term)}`?\s+(?:is|are|means|refers\s+to|consists\s+of)\s+\S", snippet, re.I))


def label(proof):
    result = BASE_LABEL(proof)
    if catalog := proof.get('catalog'):
        result += f" | catalog: {catalog['project']}@{catalog['ref']}"
    for name, title in proof.get('spellings', ()):
        result += f" | heading spelling: {name} ~ {title}"
    return result


class RelaxedBinder(ScopeBinder):
    def __init__(self, documents, identity, stamps, *, registry, question, mode):
        super().__init__(documents, identity, stamps)
        self.catalog, self.spelling, self.one_anchor = MODES[mode]
        self.registry = {p: dict(r) for p, r in registry.items()}
        self.question = question
        for path, text in documents.items():
            entry = self.registry.get(path, {})
            if (entry.get('sha256') != hashlib.sha256(text.encode()).hexdigest()
                or not all(entry.get(k) for k in ('project', 'ref', 'repository', 'commit'))):
                raise ValueError('Independent manifest must authenticate every document')
        if len({r['project'] for r in self.registry.values()}) != 1:
            raise ValueError('Mixed catalog projects are not a single binding')

    def bind(self, source):
        proof = super().bind(source)
        if proof is None:
            return None
        entry = self.registry[proof['path']]
        proof['catalog'] = ({k: entry[k] for k in ('project', 'ref', 'repository', 'commit', 'sha256')}
                            if self.catalog else None)
        names = tuple(dict.fromkeys(re.findall(r"\b[A-Za-z]+\b", self.question)))
        spellings = []
        if self.spelling:
            for name in names:
                parts = camel_words(name)
                if len(parts) < 2 or explicit_identity(self.question, name):
                    continue
                for i, h in enumerate(proof['headings']):
                    if heading_words(h['text']) != parts:
                        continue
                    if any(explicit_owners(child['text']) and not present(name, child['text'])
                           for child in proof['headings'][i + 1:]):
                        continue
                    spellings.append((name, h['text'].lstrip('# ').strip()))
        proof['spellings'] = sorted(set(spellings))
        return proof

    def heading_has(self, term, proof):
        chain = proof['headings']
        owners = [i for i, h in enumerate(chain) if present(term, h['text'])]
        if owners and not any(explicit_owners(h['text']) and not present(term, h['text'])
                              for h in chain[max(owners) + 1:]):
            return True
        return any(name.casefold() == term.casefold() for name, _ in proof.get('spellings', ()))

    def qualify(self, original, probe, source, **kwargs):
        # Exact previous policy is the control, including all its existing guards.
        before, previous = super().qualify(original, probe, source, **kwargs)
        if before.qualified or before.reason != 'insufficient_visible_match':
            return before, previous
        proof = self.bind(source)
        if proof is None or kwargs.get('evidence_text') != source.get('snippet'):
            return before, None
        terms = tuple(str(t).casefold() for t in before.trace.get('query_terms', ()))
        exact = tuple(str(t).casefold() for t in probe.get('exact_terms', ()))
        body = set(before.trace.get('body_matched_terms', ()))
        if not terms or not body:
            return before, None
        catalog = proof.get('catalog')
        def from_catalog(term):
            return bool(catalog and term == catalog['project'].casefold()
                        and not explicit_identity(self.question, term))
        def contextual(term):
            return self.heading_has(term, proof) or from_catalog(term)
        extra = {t for t in terms if contextual(t)}
        single_definition = (self.one_anchor and len(body) == 1 and bool(extra - body)
                             and definition_anchor(next(iter(body)), source['snippet'], proof))
        if len(body) < 2 and not single_definition:
            return before, None
        matched = set(before.trace.get('matched_terms', ())) | extra
        if len(matched) < 2:
            return before, None
        # Preserve existing exact-match semantics outside the explicit bindings.
        missing = [t for t in before.trace.get('missing_exact_terms', ()) if not contextual(t)]
        parent_missing = [t for t in before.trace.get('missing_parent_exact_terms', ()) if not contextual(t)]
        ratio = len(matched) / len(terms)
        threshold = 1.0 if len(terms) == 1 else 0.4 if exact else 0.5
        if missing or ratio < threshold:
            return before, None
        trace = dict(before.trace)
        trace.update(qualified=True, qualification_reason='bounded_contextual_relevance',
                     matched_terms=[t for t in terms if t in matched], matched_term_count=len(matched),
                     match_ratio=round(ratio, 4), missing_exact_terms=missing,
                     missing_parent_exact_terms=parent_missing, heading_context_used=True,
                     catalog_context_used=any(from_catalog(t) for t in terms),
                     spelling_context_used=bool(proof['spellings']), one_anchor_used=single_definition)
        return replace(before, qualified=True, covered_query_ids=(kwargs['query_id'],),
                       coverage_kind='derived' if probe.get('coverage_kind') == 'derived' else 'direct',
                       reason='bounded_contextual_relevance', trace=trace), proof


@contextmanager
def installed(binder, events):
    # Reuse the already-tested every-window instrumentation and restore on exit.
    with patch.object(section_scope, 'label', label), section_scope.installed(binder, 'scope_requalify', events):
        yield
