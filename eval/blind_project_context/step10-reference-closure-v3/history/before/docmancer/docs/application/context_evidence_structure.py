"""Source-checked fixed incoming-anchor graph for the opt-in evidence recipe.

No labels, scores, query hints or network access build this graph. Call document()
again before every forward: cached raw_document is never an authorization grant.
"""
from collections import defaultdict, deque
import hashlib
import posixpath
from urllib.parse import unquote, urlsplit

from .minimal_context_structure import (
    EVIDENCE_STRUCTURAL_RECIPE, StructuralContextError, _hydrate, _edges, _destination,
)


class EvidenceDocuments:
    def __init__(self, structure):
        if structure.recipe != EVIDENCE_STRUCTURAL_RECIPE:
            raise StructuralContextError("Evidence context requires structural v2")
        self.structure = structure
        self.incoming = defaultdict(set)
        paths = defaultdict(list)
        for identity, doc in structure.documents.items():
            self._checked_document(doc)
            paths[doc.path].append(identity)
        gaps = []
        for identity, doc in structure.documents.items():
            for index, syntax in enumerate(doc.syntax):
                pending, seen = deque(_edges(syntax, doc.definitions)), set()
                while pending:
                    kind, target = pending.popleft()
                    if (kind, target) in seen:
                        continue
                    seen.add((kind, target))
                    reason, other_id, anchor_index = None, None, None
                    if kind == "definition":
                        matches = doc.definitions.get(target, ())
                        if len(matches) != 1:
                            reason = "missing_or_ambiguous_definition"
                        elif not target.startswith("^"):
                            pending.append(("url", _destination(matches[0][1])))
                        if reason is None:
                            continue
                    else:
                        try:
                            url = urlsplit(target)
                        except ValueError:
                            reason = "invalid_link_target"
                        else:
                            if not url.fragment:
                                continue
                            path = (posixpath.normpath(posixpath.join(posixpath.dirname(doc.path), unquote(url.path)))
                                    if url.path else doc.path)
                            candidates = paths.get(path, ())
                            if url.scheme or url.netloc or url.query or len(candidates) != 1:
                                reason = "target_not_in_checked_scope"
                            else:
                                other_id = candidates[0]
                                other = structure.documents[other_id]
                                if (other.seeds[0]["_reference_evidence"]["source"]["scope"] !=
                                        doc.seeds[0]["_reference_evidence"]["source"]["scope"]):
                                    reason = "target_scope_mismatch"
                                else:
                                    matches = set(other.anchors.get(unquote(url.fragment), ()))
                                    if len(matches) != 1:
                                        reason = "missing_or_ambiguous_anchor"
                                    else:
                                        anchor_index = next(iter(matches))
                    if reason:
                        gaps.append({"reason_code": "incomplete_dependency", "path": doc.path,
                                     "char_start": doc.parents[index].char_start,
                                     "target": target, "reason": reason})
                    else:
                        self.incoming[(other_id, anchor_index)].add((identity, index))
        structure.receipt["incomplete_dependencies"] = gaps
        structure.receipt["incoming_anchor_edges"] = sum(len(v) for v in self.incoming.values())

    def _checked_document(self, doc):
        end = 0
        for index, parent in enumerate(doc.parents):
            if parent.char_start != end:
                raise StructuralContextError("Full evidence document has unchecked character gap", path=doc.path)
            _hydrate(doc, index, self.structure)
            end = parent.char_end
        if end != len(doc.raw):
            raise StructuralContextError("Full evidence document has unchecked tail", path=doc.path)

    def document(self, unit_id):
        meta = self.structure.metadata[unit_id]
        identity, index = meta["source_identity"], meta["section_index"]
        doc = self.structure.documents[identity]
        self._checked_document(doc)
        referring = set()
        for ancestor in (*doc.ancestors[index], index):
            referring.update(self.incoming.get((identity, ancestor), ()))
        entries = []
        for source_id, source_index in sorted(referring, key=lambda pair: (
                pair[0], self.structure.documents[pair[0]].parents[pair[1]].char_start,
                self.structure.documents[pair[0]].parents[pair[1]].char_end)):
            source_doc = self.structure.documents[source_id]
            parent = source_doc.parents[source_index]
            _hydrate(source_doc, source_index, self.structure)
            start = parent.char_start
            if parent.level:
                start += len(source_doc.raw[start:parent.char_end].splitlines(keepends=True)[0])
            entries.append({"source_identity": hashlib.sha256(source_id.encode()).hexdigest(),
                            "path": source_doc.path, "heading_path": list(parent.heading_path),
                            "char_start": start, "char_end": parent.char_end,
                            "text": source_doc.raw[start:parent.char_end]})
        return {"context": {"containing_document": doc.raw, "incoming_references": entries},
                "target": {"heading_path": meta["heading_path"],
                           "char_start": meta["body_char_start"], "char_end": meta["char_end"],
                           "text": doc.raw[meta["body_char_start"]:meta["char_end"]]}}
