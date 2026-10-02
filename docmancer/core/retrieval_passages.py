"""Bounded source passages, independent of display children and query prose."""
from dataclasses import dataclass
from .structured_chunking import (
    _atom_spans, _digest, _line_offsets, _span_values,
    estimate_utf8_tokens, parse_markdown_parents, TOKEN_ESTIMATOR_VERSION,
)


@dataclass(frozen=True, slots=True)
class PassageProfile:
    target_tokens: int = 512
    hard_max_tokens: int = 512
    max_atoms: int = 4096

    def __post_init__(self):
        if not 1 <= self.target_tokens <= self.hard_max_tokens <= 512:
            raise ValueError('passage limits must satisfy 1 <= target <= hard <= 512')
        if not 1 <= self.max_atoms <= 4096:
            raise ValueError('max_atoms must be between 1 and 4096')

    @property
    def identity(self):
        return _digest('source-passages-v1', TOKEN_ESTIMATOR_VERSION,
                       str(self.target_tokens), str(self.hard_max_tokens), str(self.max_atoms))


@dataclass(frozen=True, slots=True)
class RetrievalPassage:
    stable_id: str
    source_identity: str
    snapshot_id: str
    source_content_hash: str
    parent_logical_id: str
    profile_identity: str
    char_start: int
    char_end: int
    byte_start: int
    byte_end: int
    line_start: int
    line_end: int
    text: str
    token_estimate: int


@dataclass(frozen=True, slots=True)
class DeferredPassage:
    char_start: int
    char_end: int
    reason: str


def build_retrieval_passages(content, source_identity, *, snapshot_id,
                             profile=PassageProfile()):
    """Group contiguous intact atoms within one owner; never split an atom.

    Source identity must be caller-scoped (project/version/module/path).
    Returned passages are search spans, not completeness or permission claims.
    """
    if not source_identity or not snapshot_id:
        raise ValueError('source_identity and snapshot_id are required')
    _, offsets = _line_offsets(content)
    passages, deferred = [], []
    for parent in parse_markdown_parents(content, source_identity):
        atoms = _atom_spans(content, parent.char_start, parent.char_end)
        if len(atoms) > profile.max_atoms:
            deferred.append(DeferredPassage(parent.char_start, parent.char_end, 'atom_work_limited'))
            continue
        start = end = None

        def flush():
            if start is None:
                return
            text = content[start:end]
            bs, be, ls, le = _span_values(content, offsets, start, end)
            identity = _digest(profile.identity, source_identity, snapshot_id,
                               parent.source_content_hash, str(start), str(end))
            passages.append(RetrievalPassage(
                'passage-' + identity, source_identity, snapshot_id,
                parent.source_content_hash, parent.logical_id, profile.identity,
                start, end, bs, be, ls, le, text, estimate_utf8_tokens(text)))

        for atom in atoms:
            if estimate_utf8_tokens(content[atom.start:atom.end]) > profile.hard_max_tokens:
                flush()
                start = end = None
                deferred.append(DeferredPassage(atom.start, atom.end, 'oversized_atom'))
                continue
            if start is not None and estimate_utf8_tokens(content[start:atom.end]) > profile.target_tokens:
                flush()
                start = end = None
            if start is None:
                start = atom.start
            end = atom.end
        flush()
    return tuple(passages), tuple(deferred)
