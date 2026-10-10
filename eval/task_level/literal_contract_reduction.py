"""Two reviewed case selections for the existing literal-contract tests.

Compact is the default after the reviewed 2199002 CI comparison. The historical
selection remains explicitly available for reproducible diagnostic runs. This
module selects cases; it does not implement a second evaluator.
The optional pytest hook records the source actually imported by that process.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Sequence, TypeVar

T = TypeVar("T")
MODE_ENV = "DOCATLAS_LITERAL_CONTRACT_MODE"
MODES = ("historical", "compact")
TEST_FILES = (
    "tests/docs/test_question_span_coverage.py",
    "tests/test_dictionary_exit_legacy_compilers.py",
)
CASE_COUNTS = {"historical": (303, 399), "compact": (33, 49)}
COMPACT_INDICES = {
    "compiler": (0, 1, 12, 31, 40, 43, 44),
    "frames": (0, 1, 12, 43, 44),
    "wrappers": (0, 1, 12, 43, 44),
    "delegation": (0, 1),
}


def case_mode() -> str:
    value = os.environ.get(MODE_ENV, "compact")
    if value not in MODES:
        raise ValueError(f"unknown literal-contract case selection: {value!r}")
    return value


def selected_inputs(values: Sequence[T], property_id: str) -> tuple[T, ...]:
    if case_mode() == "historical":
        return tuple(values)
    return tuple(values[index] for index in COMPACT_INDICES[property_id])


def unknown_tail_pairs(prefixes: Sequence[str], tails: Sequence[str]) -> tuple[tuple[str, str], ...]:
    if case_mode() == "historical":
        # Preserve the original stacked-parametrize roster and order.
        return tuple((prefix, tail) for tail in tails for prefix in prefixes)
    if len(prefixes) < len(tails):
        raise ValueError("the reviewed compact schedule must cover every tail")
    return tuple((prefix, tails[index % len(tails)]) for index, prefix in enumerate(prefixes))


def adapter_pairs(names: Sequence[str], questions: Sequence[str]) -> tuple[tuple[str, str], ...]:
    if case_mode() == "historical":
        return tuple((name, question) for question in questions for name in names)
    # Each separate API gets a real case; there is no loop over all old inputs.
    return tuple((name, questions[(index * 3) % len(questions)]) for index, name in enumerate(names))


def adapter_variants(question: str) -> tuple[str, ...]:
    if case_mode() == "historical":
        return (question,)
    # Whitespace, Unicode, quoted syntax and an extra unknown request cannot
    # confer semantics. Every API gets this variant, including those whose base
    # example is English. Exactly two calls per compact case are counted.
    return (question, "  Ω e\u0301 `Client.  send` — " + question + " и ещё какая цена Bitcoin?\r\n")


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    """Attest imports inside the actual pytest child, including failed runs."""
    raw_path = os.environ.get("DOCATLAS_LITERAL_IMPORT_REPORT")
    if not raw_path:
        return
    root = Path.cwd().resolve()
    destination = Path(raw_path).resolve()
    destination.relative_to(root)
    expected_paths = json.loads(os.environ["DOCATLAS_LITERAL_IMPORT_PATHS"])
    identities = {}
    for relative in expected_paths:
        expected = (root / relative).resolve()
        imported_as = sorted(
            name for name, module in tuple(sys.modules.items())
            if getattr(module, "__file__", None)
            and Path(module.__file__).resolve() == expected
        )
        identities[relative] = {
            "expected_path": str(expected),
            "imported_as": imported_as,
            "imported_from_checkout": bool(imported_as),
            "sha256": hashlib.sha256(expected.read_bytes()).hexdigest(),
        }
    destination.write_text(json.dumps({
        "schema_version": 1, "mode": case_mode(), "exitstatus": int(exitstatus),
        "source_identity": identities,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
