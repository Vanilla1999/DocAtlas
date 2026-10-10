#!/usr/bin/env python3
"""Require intended recovery guard failures; crashes are not mutation kills."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GATE = "scripts/run_recovery_contract_gate.py"
CASE_ROSTER = (
    "retrieval_miss", "original_fragments", "operational_precedence", "no_semantic_retry",
    "evidence_eligibility", "documentation_gap", "authoritative_conflict", "projection_states",
    "exact_document_recovery", "literal_anchor_context", "original_discovery_attribution",
    "closed_literal_context",
)
MODULE_PATHS = {
    "docmancer.docs.application.recovery": "docmancer/docs/application/recovery.py",
    "docmancer.docs.application.proofability": "docmancer/docs/application/proofability.py",
    "docmancer.docs.interfaces.mcp.recovery_projection": "docmancer/docs/interfaces/mcp/recovery_projection.py",
    "docmancer.docs.application._project_docs_service_part03": "docmancer/docs/application/_project_docs_service_part03.py",
    "docmancer.docs.application.source_reference_evidence": "docmancer/docs/application/source_reference_evidence.py",
    "docmancer.docs.application.reference_query_tagging": "docmancer/docs/application/reference_query_tagging.py",
    "docmancer.docs.application._docs_context_projection_core": "docmancer/docs/application/_docs_context_projection_core.py",
    "docmancer.docs.domain.project_doc_ranking": "docmancer/docs/domain/project_doc_ranking.py",
    "docmancer.docs.domain.literal_context_admission": "docmancer/docs/domain/literal_context_admission.py",
    "docmancer.docs.domain.query_reference_binding": "docmancer/docs/domain/query_reference_binding.py",
    "eval.agent_developer_v1.structural_filename_controls": "eval/agent_developer_v1/structural_filename_controls.py",
    "docmancer.core._sqlite_store_part03": "docmancer/core/_sqlite_store_part03.py",
    "eval.agent_developer_v1.fts_literal_controls": "eval/agent_developer_v1/fts_literal_controls.py",
    "docmancer.docs.domain.original_body_discovery": "docmancer/docs/domain/original_body_discovery.py",
    "docmancer.docs.domain.ordinary_body_context": "docmancer/docs/domain/ordinary_body_context.py",
    "docmancer.docs.interfaces.mcp.context_tools": "docmancer/docs/interfaces/mcp/context_tools.py",
    "eval.agent_developer_v1.ordinary_body_controls": "eval/agent_developer_v1/ordinary_body_controls.py",
}
FROZEN_QUESTION_SHA256 = "2febcb8d2d4fa37fd257fb8005b453e48dfce221a6f32d19b76c0db062a7129b"
FROZEN_SOURCE_SHA256 = "17f90dd3be04d16475952da73f92d919bbe9d9b51f8e76ffa7bf0a7e64a5fc47"


@dataclass(frozen=True)
class Mutant:
    name: str
    path: str
    old: str
    new: str
    case: str
    guard: str


MUTANTS = (
    Mutant("local-handoff-auto-executes", MODULE_PATHS["docmancer.docs.application.recovery"],
           '"repeat_docs_context": False,\n            "auto_execute": False,',
           '"repeat_docs_context": False,\n            "auto_execute": True,',
           "retrieval_miss", "recovery_handoff_not_automatic"),
    Mutant("authoritative-conflict-does-not-stop", MODULE_PATHS["docmancer.docs.application.recovery"],
           '"hard_stop": True,', '"hard_stop": False,',
           "authoritative_conflict", "recovery_authoritative_conflict_stops"),
    Mutant("legacy-rephrase-regains-authority", MODULE_PATHS["docmancer.docs.application.recovery"],
           'if disposition == "rephrase_question":\n        # A legacy/supplied diagnosis cannot restore semantic retry authority.\n        return None',
           'if disposition == "rephrase_question":\n        # A legacy/supplied diagnosis cannot restore semantic retry authority.\n        return {"tool": "get_docs_context", "auto_execute": False}',
           "no_semantic_retry", "recovery_legacy_rephrase_cannot_authorize"),
    Mutant("diagnostic-invents-domain-fact", MODULE_PATHS["docmancer.docs.application.recovery"],
           'return [text] if text else []', 'return ["INVENTED_DOMAIN_FACT"] if text else []',
           "original_fragments", "recovery_original_diagnostic_fragments"),
    Mutant("eligibility-treated-as-retrieval", MODULE_PATHS["docmancer.docs.application.recovery"],
           'elif proof_origin == "eligibility":', 'elif False and proof_origin == "eligibility":',
           "evidence_eligibility", "recovery_ineligible_evidence_class"),
    Mutant("conflict-keeps-operational-action", MODULE_PATHS["docmancer.docs.interfaces.mcp.recovery_projection"],
           'if bool(diagnosis.get("hard_stop")):\n        updated["next_action"] = None',
           'if False and bool(diagnosis.get("hard_stop")):\n        updated["next_action"] = None',
           "authoritative_conflict", "recovery_conflict_suppresses_actions"),
    Mutant("operational-reason-masks-conflict", MODULE_PATHS["docmancer.docs.application.recovery"],
           'if proof_origin == "source_documentation" and "conflicting_authoritative_evidence" in proof_reasons:',
           'if not operational_reason and proof_origin == "source_documentation" and "conflicting_authoritative_evidence" in proof_reasons:',
           "authoritative_conflict", "recovery_conflict_suppresses_actions"),
    Mutant("exact-document-fallback-disabled", MODULE_PATHS["docmancer.docs.application._project_docs_service_part03"],
           'if (\n            evidence_path\n            and (current_by_exact_path.get(evidence_path) or current_by_path.get(normalize_doc_path(evidence_path)))\n        ):',
           'if (\n            False\n            and evidence_path\n            and (current_by_exact_path.get(evidence_path) or current_by_path.get(normalize_doc_path(evidence_path)))\n        ):',
           "exact_document_recovery", "recovery_exact_document_source_fact"),
    Mutant("literal-context-admission-disabled", MODULE_PATHS["docmancer.docs.domain.literal_context_admission"],
           'if qualification.qualified or qualification.reason != "insufficient_visible_match":',
           'if True or qualification.qualified or qualification.reason != "insufficient_visible_match":',
           "literal_anchor_context", "recovery_original_question_source_fact"),
    Mutant("literal-context-mints-original-credit", MODULE_PATHS["docmancer.docs.application._docs_context_projection_core"],
           '"retrieval_query_ids": [],\n                    "retrieval_query_matches": dict(original.get("retrieval_query_matches") or {}),',
           '"retrieval_query_ids": ["query-original"],\n                    "retrieval_query_matches": {"query-original": {**(original.get("retrieval_query_matches") or {}).get("query-original", {}), "qualified": True, "admission_only": False}},',
           "literal_anchor_context", "recovery_partial_no_query_credit"),
    Mutant("identifier-only-label-admitted", MODULE_PATHS["docmancer.docs.domain.literal_context_admission"],
           'if substantive:\n            witnesses.append(',
           'if True:\n            witnesses.append(',
           "literal_anchor_context", "recovery_literal_body_admission_safety"),
    Mutant("literal-context-accepts-foreign-catalog", MODULE_PATHS["docmancer.docs.domain.literal_context_admission"],
           'if not catalog_hashes or any(value != member["catalog_entry_hash"] for value in catalog_hashes):',
           'if False and (not catalog_hashes or any(value != member["catalog_entry_hash"] for value in catalog_hashes)):',
           "literal_anchor_context", "recovery_literal_snapshot_binding"),
    Mutant("later-lookup-erases-prior-public-credit", MODULE_PATHS["docmancer.docs.application._project_docs_service_part03"],
           '            matches[lookup.query_id] = trace',
           '            matches = {key: {**value, "admission_only": True} for key, value in matches.items()}\n            matches[lookup.query_id] = trace',
           "original_discovery_attribution", "retrieval_original_coverage_survives_lookups"),
    Mutant("lookup-only-hit-mints-original-discovery", MODULE_PATHS["docmancer.docs.application._project_docs_service_part03"],
           '                if lookup.origin == "original":\n                    trace["admission_only"] = True',
           '                if False and lookup.origin == "original":\n                    trace["admission_only"] = True',
           "original_discovery_attribution", "retrieval_lookup_cannot_mint_original_discovery"),
    Mutant("closed-literal-context-disabled", MODULE_PATHS["docmancer.docs.domain.literal_context_admission"],
           'closed_literal = _closed_context_literal(question)',
           'closed_literal = None',
           "closed_literal_context", "recovery_closed_literal_source_fact"),
    Mutant("closed-literal-context-ignores-extra-conditions", MODULE_PATHS["docmancer.docs.domain.literal_context_admission"],
           '        if closed:\n            return mention',
           '        if True:\n            return mention',
           "closed_literal_context", "recovery_closed_complete_syntax"),
    Mutant("requirements-context-disabled", MODULE_PATHS["docmancer.docs.domain.literal_context_admission"],
           "r\"[ \\t]+(?:do|require)\\?\\s*\"",
           "r\"[ \\t]+do\\?\\s*\"",
           "closed_literal_context", "recovery_closed_literal_source_fact"),
    Mutant("requirements-context-extra-modifier", MODULE_PATHS["docmancer.docs.domain.literal_context_admission"],
           "r\"\\s*(?:what[ \\t]+is|which[ \\t]+conditions[ \\t]+are[ \\t]+required[ \\t]+by)[ \\t]+\"",
           "r\"\\s*(?:what[ \\t]+is|which[ \\t]+(?:optional[ \\t]+)?conditions[ \\t]+are[ \\t]+required[ \\t]+by)[ \\t]+\"",
           "closed_literal_context", "recovery_closed_complete_syntax"),
    Mutant("count-context-disabled", MODULE_PATHS["docmancer.docs.domain.literal_context_admission"],
           'count_context = _closed_count_context(question)',
           'count_context = None',
           "closed_literal_context", "recovery_count_literal_source_fact"),
    Mutant("count-context-bypasses-phrase-witness", MODULE_PATHS["docmancer.docs.domain.literal_context_admission"],
           'phrase_match = re.search(technical_term_pattern(phrase, exact=True), unit_text)',
           'phrase_match = re.search(technical_term_pattern(phrase, exact=True), unit_text) or re.search(r"$", unit_text)',
           "closed_literal_context", "recovery_count_phrase_body_witness"),
    Mutant("explain-list-context-disabled", MODULE_PATHS["docmancer.docs.domain.literal_context_admission"],
           'explain_literals = _closed_explain_literals(question)',
           'explain_literals = ()',
           "closed_literal_context", "recovery_explain_literal_source_fact"),
    Mutant("explain-list-context-ignores-tail", MODULE_PATHS["docmancer.docs.domain.literal_context_admission"],
           r'if re.fullmatch(r"\.\s*", question[cursor:]) is None:',
           r'if False and re.fullmatch(r"\.\s*", question[cursor:]) is None:',
           "closed_literal_context", "recovery_explain_complete_syntax"),
    Mutant("explain-list-borrows-label-substance", MODULE_PATHS["docmancer.docs.domain.literal_context_admission"],
           'for mention in mentions:\n            remaining = re.sub(technical_term_pattern(mention.text, exact=True), "", remaining)',
           'for mention in mentions[:1]:\n            remaining = re.sub(technical_term_pattern(mention.text, exact=True), "", remaining)',
           "closed_literal_context", "recovery_explain_exact_body"),

    Mutant("filename-nomination-disabled", MODULE_PATHS["docmancer.docs.domain.query_reference_binding"],
           "    statement = document_statement_mentions(question)",
           "    statement = None",
           "closed_literal_context", "recovery_filename_source_fact"),
    Mutant("filename-collision-first-winner", MODULE_PATHS["docmancer.docs.domain.query_reference_binding"],
           "if _structural_filename_label(source.canonical_path, suffixes) == label))",
           "if _structural_filename_label(source.canonical_path, suffixes) == label))[:1]",
           "closed_literal_context", "recovery_filename_catalog_ambiguity"),
    Mutant("filename-global-recheck-only-current-source", MODULE_PATHS["docmancer.docs.domain.query_reference_binding"],
           "expected = resolve_references(item[\"question\"], catalog=catalog,",
           "expected = resolve_references(item[\"question\"], catalog=(current_source,),",
           "closed_literal_context", "recovery_filename_global_recheck"),
    Mutant("filename-target-role-not-rechecked", MODULE_PATHS["docmancer.docs.domain.query_reference_binding"],
           "                    or actual_ref[\"role\"] != expected_ref.role\n",
           "",
           "closed_literal_context", "recovery_filename_reference_roles"),
    Mutant("filename-frame-ignores-extra-clause", MODULE_PATHS["docmancer.docs.domain.query_reference_binding"],
           "r\"(?P<literal>\\w+)\\?\\s*\", question,",
           "r\"(?P<literal>\\w+)\\?(?:[ \\t]+Also\\b[^\\n]*)?\\s*\", question,",
           "closed_literal_context", "recovery_filename_complete_syntax"),
    Mutant("filename-partial-stem-becomes-locator", MODULE_PATHS["docmancer.docs.domain.query_reference_binding"],
           "if _structural_filename_label(source.canonical_path, suffixes) == label))",
           "if label in (_structural_filename_label(source.canonical_path, suffixes) or \"\")))",
           "closed_literal_context", "recovery_filename_whole_label"),
    Mutant("filename-casefold-becomes-locator", MODULE_PATHS["docmancer.docs.domain.query_reference_binding"],
           "if _structural_filename_label(source.canonical_path, suffixes) == label))",
           "if (_structural_filename_label(source.canonical_path, suffixes) or \"\").casefold() == label.casefold()))",
           "closed_literal_context", "recovery_filename_whole_label"),
    Mutant("filename-path-filter-hides-collision", MODULE_PATHS["docmancer.docs.application.source_reference_evidence"],
           "        return (tuple(self.naming_sources) if document_statement_mentions(text) is not None\n                else tuple(self.sources.values()))",
           "        return tuple(self.sources.values())",
           "closed_literal_context", "recovery_filename_path_selection_not_naming_scope"),
    Mutant("fts-primary-bare-operator-token", MODULE_PATHS["docmancer.core._sqlite_store_part03"],
           'cleaned = " ".join(literal_terms)',
           'cleaned = " ".join(terms)',
           "closed_literal_context", "recovery_fts_literal_primary"),
    Mutant("fts-fallback-bare-operator-token", MODULE_PATHS["docmancer.core._sqlite_store_part03"],
           'fallback_query = " OR ".join(literal_terms)',
           'fallback_query = " OR ".join(terms)',
           "closed_literal_context", "recovery_fts_literal_fallback"),
    Mutant("ordinary-partial-context-disabled", MODULE_PATHS["docmancer.docs.domain.ordinary_body_context"],
           "    if binding is None:\n        return None",
           "    if True:\n        return None",
           "closed_literal_context", "recovery_ordinary_full_source_fact"),
    Mutant("ordinary-native-receipt-not-required", MODULE_PATHS["docmancer.docs.domain.original_body_discovery"],
           "key in state.receipts",
           "True",
           "closed_literal_context", "recovery_ordinary_native_receipt_required"),
    Mutant("ordinary-request-owner-not-bound", MODULE_PATHS["docmancer.docs.domain.original_body_discovery"],
           "scope[\"project_id\"] != state.project_identity",
           "False",
           "closed_literal_context", "recovery_ordinary_request_owner_binding"),
    Mutant("ordinary-independent-clauses-joined", MODULE_PATHS["docmancer.docs.domain.ordinary_body_context"],
           "_BOUNDARY.finditer(text)",
           "re.finditer(r\"(?!)\", text)",
           "closed_literal_context", "recovery_ordinary_body_clause_safety"),
    Mutant("ordinary-query-content-word-skipped", MODULE_PATHS["docmancer.docs.domain.ordinary_body_context"],
           "                for source_word in source_words:\n                    if source_word[0].casefold() == query_words[cursor][0].casefold():",
           "                for source_word in source_words:\n                    if (matched and cursor + 1 < len(query_words)\n                        and source_word[0].casefold() == query_words[cursor + 1][0].casefold()):\n                        cursor += 1\n                    if source_word[0].casefold() == query_words[cursor][0].casefold():",
           "closed_literal_context", "recovery_ordinary_original_span_boundary"),
    Mutant("ordinary-literal-surface-discarded", MODULE_PATHS["docmancer.docs.domain.ordinary_body_context"],
           "    if (any(not (char.isalpha() or char.isspace() or char in \".?!,;:-–—\") for char in question)\n        or re.search(r\"(?<![^\\W\\d_])-|-(?![^\\W\\d_])\", question)\n        or query_mentions(question)",
           "    if (query_mentions(question)",
           "closed_literal_context", "recovery_ordinary_original_span_boundary"),

)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ignore(directory: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name in {".git", ".venv", ".pytest_cache", "__pycache__"}
               or name.endswith((".pyc", ".pyo"))}
    if Path(directory).is_relative_to(ROOT / "eval"):
        ignored.update(set(names) & {"results", "workspaces", "oracles", "hidden_tests"})
    return ignored


def _copy_source(destination: Path) -> None:
    for name in ("docmancer", "eval", "scripts"):
        shutil.copytree(ROOT / name, destination / name, ignore=_ignore)
    shutil.copy2(ROOT / "pyproject.toml", destination / "pyproject.toml")


def _run(copy_root: Path, evidence_root: Path, name: str, case: str | None = None) -> tuple[int, dict[str, Any]]:
    report_path = evidence_root / f"{name}.json"
    args = [sys.executable, "-B", GATE, "--report", str(report_path)]
    if case:
        args.extend(["--case", case])
    env = os.environ.copy()
    env.update(PYTHONPATH=str(copy_root), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1",
               DOCATLAS_OFFLINE="1", DOCATLAS_AUTO_VECTORS="0")
    env.pop("PYTHONOPTIMIZE", None)
    completed = subprocess.run(args, cwd=copy_root, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False)
    (evidence_root / f"{name}.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (evidence_root / f"{name}.stderr.log").write_text(completed.stderr, encoding="utf-8")
    if not report_path.is_file():
        raise RuntimeError(f"{name}: child exited {completed.returncode} without a structured report; "
                           "import/setup crashes are not kills")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return completed.returncode, report


def _validate_report(report: dict[str, Any], *, hashes: dict[str, str], roster: tuple[str, ...],
                     returncode: int, mutant: Mutant | None = None) -> None:
    if (report.get("schema_version") != "recovery-contract-v2"
        or report.get("question_sha256") != FROZEN_QUESTION_SHA256
        or report.get("source_sha256") != FROZEN_SOURCE_SHA256):
        raise RuntimeError("recovery report schema or original task/source identity differs")
    modules = report.get("modules")
    if (not isinstance(modules, list) or len(modules) != len(MODULE_PATHS)
        or {row.get("module") for row in modules} != set(MODULE_PATHS)):
        raise RuntimeError("recovery module import roster differs")
    for row in modules:
        path = MODULE_PATHS[row["module"]]
        if row.get("path") != path or row.get("sha256") != hashes[path]:
            raise RuntimeError(f"recovery executed foreign/stale source: {row}")
    rows = report.get("cases")
    if not isinstance(rows, list) or tuple(row.get("id") for row in rows) != roster:
        raise RuntimeError("recovery testcase roster differs or is incomplete")
    if any(row.get("outcome") not in {"passed", "failure", "error"} for row in rows):
        raise RuntimeError("recovery testcase has an unknown/skipped outcome")
    counts = {outcome: sum(row["outcome"] == outcome for row in rows)
              for outcome in ("passed", "failure", "error")}
    if counts != report.get("counts"):
        raise RuntimeError("recovery report counts disagree with individual outcomes")
    if mutant is None:
        if returncode != 0 or counts != {"passed": len(roster), "failure": 0, "error": 0}:
            raise RuntimeError(f"recovery baseline is not fully green: {counts}; returncode={returncode}")
    elif (returncode != 1 or counts != {"passed": 0, "failure": 1, "error": 0}
          or roster != (mutant.case,) or rows[0].get("guard") != mutant.guard):
        raise RuntimeError(f"{mutant.name}: no intended guard kill; {rows}; returncode={returncode}")


def _verify_report_rejections(baseline: dict[str, Any], hashes: dict[str, str]) -> None:
    """Negative controls for the evaluator, without invoking project code again."""
    mutant = MUTANTS[0]
    expected = deepcopy(baseline)
    expected["cases"] = [{"id": mutant.case, "outcome": "failure", "guard": mutant.guard}]
    expected["counts"] = {"passed": 0, "failure": 1, "error": 0}
    _validate_report(expected, hashes=hashes, roster=(mutant.case,), returncode=1, mutant=mutant)
    controls = []
    wrong_guard = deepcopy(expected)
    wrong_guard["cases"][0]["guard"] = "unrelated_assertion"
    controls.append(("wrong_guard", wrong_guard, 1))
    error = deepcopy(expected)
    error["cases"][0] = {"id": mutant.case, "outcome": "error", "error_type": "ImportError"}
    error["counts"] = {"passed": 0, "failure": 0, "error": 1}
    controls.append(("import_error", error, 1))
    missing = deepcopy(expected)
    missing["cases"] = []
    missing["counts"] = {"passed": 0, "failure": 0, "error": 0}
    controls.append(("missing_case", missing, 1))
    foreign = deepcopy(expected)
    foreign["modules"][0]["path"] = "/foreign/installed/recovery.py"
    controls.append(("foreign_import", foreign, 1))
    stale = deepcopy(expected)
    stale["modules"][0]["sha256"] = "0" * 64
    controls.append(("stale_module", stale, 1))
    controls.append(("wrong_exit_code", deepcopy(expected), 2))
    for name, report, code in controls:
        try:
            _validate_report(report, hashes=hashes, roster=(mutant.case,), returncode=code, mutant=mutant)
        except RuntimeError:
            continue
        raise RuntimeError(f"recovery evaluator accepted invalid evidence: {name}")
    print("EVALUATOR CONTROLS: rejected " + ", ".join(name for name, _, _ in controls))


def main() -> int:
    temp_base = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    evidence_root = Path(tempfile.mkdtemp(prefix="docatlas-recovery-evidence-", dir=temp_base))
    copy_root = Path(tempfile.mkdtemp(prefix="docatlas-recovery-mutation-", dir=temp_base))
    try:
        _copy_source(copy_root)
        gate_sha256 = _digest(copy_root / GATE)
        hashes = {path: _digest(copy_root / path) for path in MODULE_PATHS.values()}
        code, baseline = _run(copy_root, evidence_root, "baseline")
        _validate_report(baseline, hashes=hashes, roster=CASE_ROSTER, returncode=code)
        _verify_report_rejections(baseline, hashes)
        print("EVIDENCE: " + json.dumps({"run": "baseline", "returncode": code,
                                        "gate_sha256": gate_sha256, "report": baseline}, sort_keys=True))
        for mutant in MUTANTS:
            path = copy_root / mutant.path
            original = path.read_bytes()
            source = original.decode("utf-8")
            if source.count(mutant.old) != 1:
                raise RuntimeError(f"{mutant.name}: patch anchor count={source.count(mutant.old)}, expected 1")
            changed = source.replace(mutant.old, mutant.new, 1).encode("utf-8")
            if changed == original:
                raise RuntimeError(f"{mutant.name}: mutation did not change source")
            path.write_bytes(changed)
            try:
                mutated_hashes = {relative: _digest(copy_root / relative) for relative in MODULE_PATHS.values()}
                altered = [relative for relative in hashes if mutated_hashes[relative] != hashes[relative]]
                if altered != [mutant.path] or _digest(copy_root / GATE) != gate_sha256:
                    raise RuntimeError(f"{mutant.name}: mutation altered an unexpected source/oracle")
                code, report = _run(copy_root, evidence_root, mutant.name, mutant.case)
                _validate_report(report, hashes=mutated_hashes, roster=(mutant.case,), returncode=code, mutant=mutant)
                if (_digest(copy_root / GATE) != gate_sha256
                    or any(_digest(copy_root / relative) != digest for relative, digest in mutated_hashes.items())):
                    raise RuntimeError(f"{mutant.name}: child modified the source/oracle during execution")
                mutation = {"name": mutant.name, "path": mutant.path, "case": mutant.case,
                            "expected_guard": mutant.guard, "before_sha256": hashes[mutant.path],
                            "after_sha256": mutated_hashes[mutant.path]}
                print("EVIDENCE: " + json.dumps({"run": mutant.name, "returncode": code,
                                                "mutation": mutation, "report": report}, sort_keys=True))
                print(f"KILLED: {mutant.name} by {mutant.case}:{mutant.guard}")
            finally:
                path.write_bytes(original)
        summary = {"status": "passed", "baseline_cases": len(CASE_ROSTER), "mutants_killed": len(MUTANTS),
                   "gate_sha256": gate_sha256, "frozen_question_sha256": FROZEN_QUESTION_SHA256,
                   "frozen_source_sha256": FROZEN_SOURCE_SHA256}
        (evidence_root / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"FAIL: recovery mutation evidence rejected: {error}", file=sys.stderr)
        print(f"evidence retained at {evidence_root}; source copy retained at {copy_root}", file=sys.stderr)
        return 1
    shutil.rmtree(copy_root)
    print(f"PASS: all {len(CASE_ROSTER)} baseline cases green; {len(MUTANTS)} intended guard kills; evidence at {evidence_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
