"""Narrow AST classifications; do not infer technical safety from symbol names."""
from __future__ import annotations

import ast


# These modules were read completely for this audit. Source pins are enforced by
# the caller; retaining DTO/serialization does not retain semantic producers.
REVIEWED_TECHNICAL_MODULES = {
    "docmancer/docs/application/evidence_models.py": "Immutable DTOs, explicit enum/bounds validation and serialization of supplied requirements/support verdicts; no NL-to-obligation mapping",
    "docmancer/retrieval/contracts.py": "Explicit retrieval DTOs, configured fields, provenance/hash/budget validation; field producers and authority interpretation audited separately",
    "docmancer/core/html_utils.py": "HTML grammar/entity decoding and structural tag extraction; fixed markup tags are not query topics",
    "docmancer/context.py": "Explicit output-style dispatch, XML escaping and ordered budget fitting; generic prompt uses provided instruction/question, not product substitutions",
    "docmancer/docs/domain/target_security.py": "HTTP scheme/host/IP/path authorization from explicit URL and allowlists; not question-driven topic filtering",
    "docmancer/docs/domain/source_identity.py": "Serialization/classification of explicit registry/source/version inputs; label correctness does not certify producer freshness",
    "docmancer/docs/infrastructure/storage_mutation_lock.py": "OS locks, errno/platform identities, writer leases and bounded cleanup barriers; no natural-language question interpretation",
    "docmancer/docs/domain/query_script_runs.py": "Bounded verbatim Latin runs detected by character/script grammar; no translation, synonym insertion or derived original-query proof",
    "docmancer/docs/domain/source_subject_binding.py": "Current raw-body digest/window/structural-owner equality validation; no catalog/title-derived authorization",
    "docmancer/docs/application/context_quality.py": "Explicit projected mandatory/covered/missing IDs and unresolved residue determine packet quality; producer completeness proofs must be audited separately",
    "docmancer/docs/interfaces/mcp/docs_context_routing.py": "Explicit lookup array validation/deduplication, tuple input normalization and iterative serialized budget estimate; no query decomposition requirement",
    "docmancer/support_policy.py": "Shipped surface IDs, support-tier schema validation and CLI tier labeling; not question routing or answer inference; external policy text remains separate",
    "docmancer/docs/domain/policies.py": "Timestamp age validation and explicit registered-source webfetch policy; preserve network/source authorization independently of semantic migration",
}

REVIEWED_SYMBOLS = {
    ("docmancer/docs/interfaces/mcp/error_contract.py", "assignment:_RETRYABLE_BY_REASON"): ("TECH-ERROR", "TECHNICAL-RETAIN-CANDIDATE", "Exact structured reason-code to retryability protocol mapping; no free-text matching"),
    ("docmancer/docs/interfaces/mcp/error_contract.py", "assignment:_VALIDATION_REASON_CODES"): ("TECH-ERROR", "TECHNICAL-RETAIN-CANDIDATE", "Explicit validation error enum"),
    ("docmancer/docs/interfaces/mcp/error_contract.py", "assignment:_HINTS_BY_REASON"): ("D33", "SPLIT", "Reason-code keyed caller workflow instructions and illustrative library examples; approval/retry guidance must stay consistent with canonical contract"),
    ("docmancer/docs/interfaces/mcp/error_contract.py", "_retryable_for"): ("TECH-ERROR", "TECHNICAL-RETAIN-CANDIDATE", "Structured reason-code dispatch with fail-closed unknown code"),
    ("docmancer/docs/interfaces/mcp/error_contract.py", "_hints_for"): ("D33", "SPLIT", "Copies explicit caller hints or reason-keyed guidance; no evidence/proof authorization from hint text"),
    ("docmancer/docs/interfaces/mcp/error_contract.py", "build_mcp_error_payload"): ("TECH-ERROR", "TECHNICAL-RETAIN-CANDIDATE", "Bounded error serialization/debug redaction, not documentary proof; hints content producer separately SPLIT"),
    ("docmancer/docs/interfaces/mcp/error_contract.py", "_bounded_warning"): ("TECH-ERROR", "TECHNICAL-RETAIN-CANDIDATE", "Warning protocol field allowlist and bounded values"),
}

# Mixed module decisions are migration scope, not permission to retain every
# nested recognizer. Exact local spans and source/security guards survive;
# hardcoded natural-language interpretation does not.
REVIEWED_MIXED_MODULES = {
    "docmancer/docs/domain/answer_completeness.py": ("D27", "Story/layer/action lists and Russian product-like requirement patterns drive extraction, coverage, navigation and source-search handoff; preserve negative/absent-evidence rejection and canonical support override, audit legacy next-actions/edit-ready consumers separately"),
    "docmancer/docs/domain/source_map.py": ("D31", "Status lexical list, query stopwords, declaration suffix priority and question-derived generated-file inclusion affect recall/evidence; preserve bounded source traversal, exact source lines, syntax/AST extraction, redaction and absence-not-proof separately; fuzzy matching is not a semantic dictionary but not proof either"),
    "docmancer/docs/domain/project_doc_ranking.py": ("D13", "Question-lane regexes, path-derived taxonomy/authority, artifact/history gates, topical boosts and broad source injection affect selection; preserve source freshness, explicit qualification failures, bounded diversity and independent public-query attribution separately"),
    "docmancer/docs/domain/snippets.py": ("D16", "Question-to-language/library-symbol invention, intent boosts, UI-noise lists and library-based language inference affect snippet selection; preserve actual fenced bytes, supplied provenance/version risk, truncation flags, source caps and support-insufficiency confidence reduction separately"),
    "docmancer/docs/domain/normative_language.py": ("D25", "English normative modality/definition recognizers select required/forbidden; separately preserve bounded AST-validated Python declaration exclusion"),
    "docmancer/docs/domain/context_request_preferences.py": ("D35", "Code/signature/default-timeout/origin-comparison lexical cues affect preference and stopping; preserve literal fence completeness, offsets and generic echo check"),
    "docmancer/docs/application/evidence_semantic_density.py": ("D36", "Normative/action lists and generic-scope stop tokens affect local match/ranking; preserve explicit requested-source binding and config-value syntax separately"),
    "docmancer/docs/domain/admission_local_binding.py": ("D21", "Default-property rewriting, English condition/state/anaphora and duration/action grammar influence witness proof; preserve subject-local spans, unsupported-condition rejection and no heading/title authorization"),
    "docmancer/docs/domain/context_hint_policy.py": ("D19", "Fallback calls dictionary-backed _specific_contract_request/_tokens; preserve partial-only attribution, current-body requalification, scope/identity/freshness and projection budget checks"),
    "docmancer/docs/domain/lifecycle_policy.py": ("D18", "Exact active/current/completed metadata filters are technical policy; lifecycle_intent delegates question meaning to lexical contract parser; keep snapshot checks separately"),
    "docmancer/docs/application/context_query_probes.py": ("D26", "Independent original/host/retrieval-need body requalification delegates role extraction and reference proof; preserve original admission-only flag, distinct host evidence, no path-substring support and structural revalidation"),
    "docmancer/docs/application/project_answer_outline.py": ("D13", "README/architecture/mcp filename and heading guesses assign source reasons; keyword cooccurrence synthesizes coverage flags; retain ordered actual source provenance/caps, not inferred completeness"),
}


def classify_node(node: ast.AST, *, path: str, assignment: list[str], parent: dict[ast.AST, ast.AST], owner: str = ""):
    identity = owner or "assignment:" + ",".join(assignment)
    if (path, identity) in REVIEWED_SYMBOLS:
        return REVIEWED_SYMBOLS[path, identity]
    if path in REVIEWED_TECHNICAL_MODULES:
        return "TECH-CONTRACT", "TECHNICAL-RETAIN-CANDIDATE", REVIEWED_TECHNICAL_MODULES[path]
    if path in REVIEWED_MIXED_MODULES:
        group, reason = REVIEWED_MIXED_MODULES[path]
        return group, "SPLIT", reason
    # A Literal type declares permitted exact protocol values, not an NL matcher.
    # The consumer selecting that value from free text is a separate candidate.
    enclosing = parent.get(node)
    if (isinstance(node, ast.Tuple) and isinstance(enclosing, ast.Subscript)
            and isinstance(enclosing.value, ast.Name) and enclosing.value.id == "Literal"
            and all(isinstance(item, ast.Constant) for item in node.elts)):
        return "TECH-ENUM", "TECHNICAL-RETAIN-CANDIDATE", "Literal type enum only; no exemption for NL producer/consumer or default authorization"
    # Direct same-name field copying only. Do not treat strings->strings, keyword
    # dispatch to function names, or renamed attributes as generic serialization.
    if isinstance(node, ast.Dict) and node.keys:
        def same_field(key, value):
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                return False
            if isinstance(value, ast.Name):
                return key.value == value.id
            if isinstance(value, ast.Attribute):
                return key.value == value.attr
            if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                    and value.func.id in {"list", "tuple"} and len(value.args) == 1 and not value.keywords):
                return same_field(key, value.args[0])
            return False
        same_name = all(same_field(key, value) for key, value in zip(node.keys, node.values))
        if same_name:
            return "TECH-FIELD-COPY", "TECHNICAL-RETAIN-CANDIDATE", "Exact same-name field pass-through; value origin and flag certification remain separate"
    if (assignment == ["__all__"] and isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr == "startswith"
            and len(node.args) == 1 and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str) and node.args[0].value.startswith("_")):
        return "TECH-EXPORT", "TECHNICAL-RETAIN-CANDIDATE", "Private/shard Python export-name filter; exported implementations remain in scope"
    return None
