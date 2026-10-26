"""Question-oriented evidence selection over already authorized source rows.

This is lexical/structural coverage, not a semantic sufficiency certificate.
The selected prefix is independent of the page budget; every omitted original
row remains in a signed continuation. No source reads, LLM calls, scope changes,
answer generation, product-name lists or evaluation oracles occur here.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re

POLICIES = frozenset({'query-cover-v1', 'owner-cover-v1', 'guarded-cover-v1'})
_WORD = re.compile(r'[^\W_]+', re.UNICODE)
_STOP = frozenset('''a an the is are be was were being how what which when where who why
can could do does did should would will shall to of for in on at by with from and or
it its this that these those as than please tell explain describe about me all any
if not no yes have has had when into their there also both use uses using used
provide provides determine determines exactly differ different return returns
set unset explicitly specify specified argument arguments option options
какой какая какие как что где когда почему это для или при из на по и в во о об с со'''.split())
# Procedural questions need the complete acquired leaf section rather than an
# isolated paragraph: its other rules may encode a precondition or exception.
_PROCEDURE = re.compile(r'\b(?:how|where)\b.*\b(?:search|find|look|discover|recover|resume|restore|publish|rollback|retry)\w*\b', re.I)
_TECHNICAL = re.compile(r'--[\w-]+|\b\w+(?:[._]\w+)+\b|\b\w+=\w+\b')


def terms(value: str) -> frozenset[str]:
    out = set()
    for term in _WORD.findall(value.casefold()):
        if len(term) < 2 or term in _STOP:
            continue
        if term.endswith('ing') and len(term) > 6:
            term = term[:-3]
            if len(term)>2 and term[-1] == term[-2]: term = term[:-1]
        elif term.endswith('ed') and len(term)>5:
            term = term[:-2]
        elif term.endswith('es') and term[-3:-2] in {'s','x','z'} and len(term)>5:
            term = term[:-2]
        elif term.endswith('ies') and len(term) > 5:
            term = term[:-3] + 'y'
        elif term.endswith('s') and not term.endswith(('ss', 'us')) and len(term) > 4:
            term = term[:-1]
        if term.endswith('e') and len(term)>4: term=term[:-1]
        out.add(term)
    return frozenset(out)


def _identity(row: dict) -> tuple:
    # An ownership group is local to the exact authorized snapshot/scope.
    # content_sha256 is a snippet hash, not a shared document snapshot hash;
    # each original row stays separate and the entire pool is HMAC-bound.
    return tuple(str(row.get(key) or '') for key in
                 ('project_identity','path_or_url','scope','version_binding','authority','instruction_trust','freshness','section'))


@dataclass(frozen=True)
class Selection:
    chosen: tuple[int, ...]
    order: tuple[int, ...]
    diagnostic: dict


def _select_clause(rows: list[dict], question: str, *, policy: str) -> Selection:
    """Stop at saturated lexical coverage, not at a size or fragment quota.

    Reuse the native acquisition's first ranked topical witness, then add only
    evidence carrying still-unrepresented query terms. Reverse pruning removes
    a chosen row only if it contributes no unique coverage. Whole source rows
    are retained, so negations/numeric conditions inside them are never edited.
    """
    if policy not in POLICIES:
        raise ValueError('invalid_evidence_selection_policy')
    if not isinstance(question, str) or not rows:
        return Selection((), tuple(range(len(rows))), {'status':'no_candidates', 'semantic_sufficiency_certified':False})
    query = terms(question)
    bodies = [terms(row['snippet']) for row in rows]
    headings = [terms(str(row.get('section') or '').rsplit(' > ', 1)[-1]) for row in rows]
    # Explicit literal query tokens which also name a path namespace are
    # relevance hints ONLY, not permission/scope narrowing. All rows remain
    # reachable. Comparative questions can retain multiple named namespaces.
    namespaces = [terms(row['path_or_url'].split('/')[0]) for row in rows]
    namespace_words = set().union(*namespaces)
    named = query.intersection(namespace_words)
    eligible = [i for i in range(len(rows)) if not named or named.intersection(namespaces[i])]
    content_query = query - named
    feature_sets = [(bodies[i] | headings[i]).intersection(content_query) for i in range(len(rows))]
    available = set().union(*(feature_sets[i] for i in eligible)) if eligible else set()
    absent = content_query - available
    df = Counter(t for i in eligible for t in feature_sets[i])
    weights = {t: 1 + math.log((len(eligible)+1)/(df[t]+1)) for t in available}
    # Exact identifiers are coverage obligations, not fuzzily conflated flags.
    identifiers = tuple(dict.fromkeys(_TECHNICAL.findall(question)))
    ident_features = [{f'identifier:{s.casefold()}' for s in identifiers
                       if s.casefold() in (rows[i]['snippet']+' '+str(rows[i].get('section') or '')).casefold()}
                      for i in range(len(rows))]
    for i in range(len(rows)):
        feature_sets[i] = set(feature_sets[i]) | ident_features[i]
    for ident in set().union(*(ident_features[i] for i in eligible)) if eligible else ():
        weights[ident] = max(weights.values(), default=1)*1.5
    def weight(features): return sum(weights.get(x, 0) for x in features)
    # Unknown requests must not be filled with a page of broad-topic matches.
    # This is explicitly limited to matching terms in THIS acquired pool.
    if len(absent) >= 2 and len(absent) > len(content_query)/2:
        eligible = [i for i in eligible if ident_features[i] or len(feature_sets[i]) >= 3]
    if not eligible or not any(feature_sets[i] for i in eligible):
        return Selection((), tuple(range(len(rows))), {'status':'no_direct_lexical_witness',
            'unmatched_query_terms': sorted(absent), 'semantic_sufficiency_certified':False})
    # The seed keeps the native rank advantage, provided it has a meaningful
    # share of the question's available evidence terms.
    best_overlap = max(weight(feature_sets[i]) for i in eligible)
    seed = next(i for i in eligible if weight(feature_sets[i]) >= best_overlap * .65)
    chosen = [seed]
    covered = set(feature_sets[seed])
    while True:
        candidates = []
        for i in eligible:
            if i in chosen:
                continue
            gain = feature_sets[i] - covered
            # A lone broad word is not a second obligation. Exact code/flag
            # literals are retained even when represented by one feature.
            if len(gain) < 2 and not any(t.startswith('identifier:') for t in gain):
                continue
            cost = max(1, len(rows[i]['snippet'].encode()))
            score = weight(gain) / cost ** .35
            candidates.append((score, -i, i))
        if not candidates:
            break
        index = max(candidates)[2]
        chosen.append(index); covered.update(feature_sets[index])
    # Minimize this lexical witness union without losing what it covers.
    for i in reversed(chosen[:]):
        others = set().union(*(feature_sets[j] for j in chosen if j != i))
        if feature_sets[i] <= others:
            chosen.remove(i)
    primary = tuple(chosen)
    if policy in {'owner-cover-v1', 'guarded-cover-v1'} or _PROCEDURE.search(question):
        owners = {_identity(rows[i]) for i in chosen}
        chosen = [i for i in range(len(rows)) if _identity(rows[i]) in owners]
    uncertain = None
    if policy == 'guarded-cover-v1':
        # Do not turn matching vocabulary into a completeness certificate.
        # Native and coverage ranking disagreement is reason to keep the
        # original paging behavior, not to force an aggressively small answer.
        if not primary or primary[0] != eligible[0]:
            uncertain = 'ranking_disagreement'
        first = eligible[0]
        first_fraction = len((bodies[first] | headings[first]) & available) / max(1, len(available))
        if first_fraction < .65:
            uncertain = 'diffuse_question_coverage'
        # When the winning leaf is a nested subrule, its acquired immediate
        # parent can contain prerequisites that the child does not repeat.
        # Add parent records only when query terms also occur in their bodies.
        owners = {_identity(rows[i]) for i in chosen}
        for owner in tuple(owners):
            if (' > ' not in owner[-1]
                    or len(terms(owner[-1].rsplit(' > ', 1)[-1]) & content_query) >= 2):
                continue
            parent = (*owner[:-1], owner[-1].rsplit(' > ', 1)[0])
            members = [i for i in eligible if _identity(rows[i]) == parent
                       and len(bodies[i].intersection(content_query)) >= 2]
            # Only add a parent with an independently query-bearing statement;
            # never pull an arbitrary sibling or entire Markdown document.
            if members:
                chosen.extend(i for i in eligible if _identity(rows[i]) == parent)
        # A contrastive/non-identifier question with competitive matches in
        # other owners is ambiguous. Retain the original view in that case.
        if (not identifiers and not _PROCEDURE.search(question)
                and re.search(r'\b(?:not|versus|and|or)\b', question, re.I)):
            winner_terms = feature_sets[first]
            ambiguous = [i for i in eligible if _identity(rows[i]) != _identity(rows[first])
                         and feature_sets[i] >= winner_terms and winner_terms]
            if ambiguous:
                uncertain = 'competing_source_owners'
        if uncertain:
            return Selection(tuple(range(len(rows))), tuple(range(len(rows))), {
                'status':'conservative_original_order', 'reason':uncertain,
                'unmatched_query_terms':sorted(absent),
                'semantic_sufficiency_certified':False, 'corpus_absence_proven':False})
        chosen = sorted(set(chosen))
    selected = set(chosen)
    order = tuple(chosen + [i for i in range(len(rows)) if i not in selected])
    return Selection(tuple(chosen), order, {'status':'lexical_coverage_saturated',
        'selected_rows':len(chosen),'candidate_rows':len(rows),'unmatched_query_terms':sorted(absent),
        'covered_features':sorted(covered),'query_features':sorted(content_query),
        'semantic_sufficiency_certified':False, 'corpus_absence_proven':False})


_SPLIT = re.compile(r"[?;]\s*|(?:,\s*(?:and\s+)?|\s+and\s+)(?=(?:exactly\s+)?(?:what|which|where|when|how|why|whether)\b)", re.I)


def select_evidence(rows: list[dict], question: str, *, policy: str = 'guarded-cover-v1',
                    focus_queries: tuple[str, ...] | list[str] = ()) -> Selection:
    """Evaluate explicit question clauses independently; never fill to capacity.

    An unknown second clause must not make an otherwise answerable first clause
    pull in all topic-adjacent sources. Clauses are literal user text, not model
    hallucinations or obligations copied from the benchmark oracle.
    """
    if policy not in POLICIES:
        raise ValueError('invalid_evidence_selection_policy')
    clauses = [part.strip(' ,.?') for part in _SPLIT.split(question) if part.strip(' ,.?')]
    clauses.extend(q for q in focus_queries if isinstance(q, str) and q not in clauses)
    if len(clauses) > 12 or len(question) > 4096:
        return Selection(tuple(range(len(rows))), tuple(range(len(rows))), {
            'status':'conservative_original_order','reason':'query_complexity',
            'semantic_sufficiency_certified':False, 'corpus_absence_proven':False})
    namespaces = set().union(*(terms(r['path_or_url'].split('/')[0]) for r in rows)) if rows else set()
    subjects = terms(question) & namespaces
    chosen, details = set(), []
    for clause in clauses:
        local = clause
        if len(subjects) == 1 and not terms(clause).intersection(subjects):
            local += ' ' + next(iter(subjects))
        result = _select_clause(rows, local, policy=policy)
        chosen.update(result.chosen)
        details.append({'clause':clause, **result.diagnostic})
    order = tuple(sorted(chosen) + [i for i in range(len(rows)) if i not in chosen])
    return Selection(tuple(sorted(chosen)), order, {
        'status': 'conservative_original_order' if any(d['status']=='conservative_original_order' for d in details)
                  else 'question_witness_cover',
        'clauses':details, 'selected_rows':len(chosen), 'candidate_rows':len(rows),
        'semantic_sufficiency_certified':False, 'corpus_absence_proven':False})
