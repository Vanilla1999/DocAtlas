"""Data-only helpers for the frozen pre-MiniLM comparison.

No product imports and no gold is read by the execution driver. NEW20 sealed
inputs are opened only after a coordinator's code/config freeze is verified.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import sys

ARMS = ("main", "retrieval_text", "rrf")
DATASETS = {"v40": ("eval/prepared_model_comparison40", 40),
            "new20": ("eval/heuristic_removal_holdout", 20)}
PREFIXES = (5, 10, 20, 40, 100, 256)


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def read(path: Path):
    return json.loads(path.read_bytes())


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load frozen evaluation helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_freeze(repo: Path, path: Path, *, holdout: bool) -> dict:
    frozen = read(path)
    if frozen.get("code_config_frozen") is not True:
        raise ValueError("coordinator code/config freeze is required")
    if holdout and frozen.get("holdout_open_after_freeze") is not True:
        raise ValueError("NEW20 must remain sealed until coordinator freeze")
    inputs = frozen.get("inputs_sha256")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("missing frozen input hashes")
    for relative, expected in inputs.items():
        p = PurePosixPath(relative)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("freeze path must remain inside the repository")
        target = repo / relative
        if not target.is_file() or sha(target.read_bytes()) != expected:
            raise ValueError("frozen input changed: " + relative)
    required = ["eval/prepared_model_comparison40/questions.json",
                "eval/prepared_model_comparison40/gold_spans.json",
                "eval/prepared_model_comparison40/source_plan.json"]
    if holdout:
        required += ["eval/heuristic_removal_holdout/sealed/questions.json",
                     "eval/heuristic_removal_holdout/sealed/oracle.json",
                     "eval/heuristic_removal_holdout/FREEZE_MANIFEST.json",
                     "eval/heuristic_removal_holdout/source-manifest.json"]
    required += ["eval/evidence_quality_v2/runtime.py", "eval/heuristic_removal/receipts.py",
                 "eval/heuristic_removal/assess.py", "eval/prepared_model_comparison40/evaluate.py"]
    required += [p.relative_to(repo).as_posix() for p in (repo / "eval/preminilm_retrieval").glob("*.py")]
    if any(name not in inputs for name in required):
        raise ValueError("freeze omits a required unchanged corpus/oracle")
    if not frozen.get("baseline_sha") or not frozen.get("candidate_sha"):
        raise ValueError("exact baseline/candidate refs must be recorded")
    arms = frozen.get("arms", {})
    if (set(arms) != set(ARMS) or any(arms[name].get("policy") != name for name in ARMS)
            or arms["rrf"].get("rrf_k") != 60 or arms["rrf"].get("raw_row_allocation") != [128, 128]):
        raise ValueError("missing or changed frozen experimental policies")
    return frozen


def dataset(repo: Path, name: str) -> tuple[list[dict], dict[str, list[str]]]:
    directory = repo / DATASETS[name][0]
    if name == "v40":
        cases = read(directory / "questions.json")["cases"]
        families = {r["id"]: r["paths"] for r in read(directory / "source_plan.json")["families"]}
    else:
        # Caller has verified coordinator freeze before reaching this branch.
        original = read(directory / "FREEZE_MANIFEST.json")
        for row in original["files"]:
            if sha((directory / row["path"]).read_bytes()) != row["sha256"]:
                raise ValueError("independently frozen NEW20 input changed")
        cases = read(directory / "sealed/questions.json")["cases"]
        families = {}
        for row in read(directory / "source-manifest.json")["sources"]:
            group = row["project_group"]
            suffix = PurePosixPath(row["path"]).relative_to(PurePosixPath("corpus") / group)
            families.setdefault(group, []).append(suffix.as_posix())
    if len(cases) != DATASETS[name][1] or len({r["id"] for r in cases}) != len(cases):
        raise ValueError("frozen case count or identity changed")
    if any(c["project_group"] not in families or not isinstance(c["question"], str) for c in cases):
        raise ValueError("invalid frozen question binding")
    return cases, families


def documents(repo: Path, name: str, family: str, paths: list[str]) -> dict[str, str]:
    directory = repo / DATASETS[name][0] / ("sources" if name == "v40" else "corpus") / family
    result = {}
    for relative in paths:
        target = (directory / relative).resolve()
        if not target.is_relative_to(directory.resolve()):
            raise ValueError("source escapes its frozen family")
        result[relative] = target.read_bytes().decode("utf-8")
    return result


def rows_from_wire(payload: dict) -> list[dict]:
    """Independently expand documented transport layouts; never authorize rows."""
    value = deepcopy(payload)
    fmt = value.get("context_format", "")
    if fmt in {"docatlas.sections.v1", "docatlas.sections.v2"}:
        rows = {}
        defaults = value["source_defaults"]
        for group in value["source_groups"]:
            common = group["common"]
            if set(defaults) & set(common):
                raise ValueError("overlapping section defaults")
            for fragment in group["fragments"]:
                i, fields = fragment["index"], fragment["fields"]
                if (type(i) is not int or i < 0 or i in rows
                        or set(fields) & (set(defaults) | set(common))):
                    raise ValueError("ambiguous section fragment")
                rows[i] = {**defaults, **common, **fields}
        if sorted(rows) != list(range(len(rows))):
            raise ValueError("noncontiguous section fragments")
        return [rows[i] for i in range(len(rows))]
    rows = value.get("sources", [])
    if str(fmt).startswith("docatlas.assembled-"):
        kind = fmt.removeprefix("docatlas.assembled-").removesuffix(".v1")
        if kind not in {"grouped", "table", "grouped-table"}:
            raise ValueError("unknown assembled format")
        if kind in {"table", "grouped-table"}:
            columns = value["source_columns"]
            if len(columns) != len(set(columns)):
                raise ValueError("duplicate source columns")
            if any(not isinstance(r, list) or len(r) != len(columns) for r in rows):
                raise ValueError("source row width mismatch")
            rows = [dict(zip(columns, r, strict=True)) for r in rows]
        if kind in {"grouped", "grouped-table"}:
            groups = value["source_groups"]
            decoded = []
            for row in rows:
                index = row.pop("group")
                if type(index) is not int or not 0 <= index < len(groups) or set(row) & set(groups[index]):
                    raise ValueError("invalid group reference")
                decoded.append({**groups[index], **row})
            rows = decoded
    if fmt == "docatlas.standalone-text.v1" or str(fmt).startswith("docatlas.assembled-"):
        normalized = []
        for row in rows:
            r = {**value.get("source_context", {}), **row}
            normalized.append({**r, "path_or_url": r["path"], "snippet": r["text"],
                               "evidence_id": r["ref"]})
        return normalized
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError("invalid canonical source rows")
    return rows


def source_intervals(rows: list[dict], docs: dict[str, str], root: str, *, candidate: bool = False,
                     generation: str | None = None):
    """Validate exact bytes and coordinates; ambiguous placements earn intersection only."""
    intervals, failures, identities = {}, [], set()
    for index, row in enumerate(rows):
        try:
            path = row.get("path") if candidate else row.get("path_or_url")
            path = path or row.get("source")
            p = PurePosixPath(path)
            if p.is_absolute():
                p = p.relative_to(PurePosixPath(root))
            if ".." in p.parts or p.as_posix() not in docs:
                raise ValueError("outside frozen source family")
            relative = p.as_posix()
            raw = docs[relative]
            text = row["text"] if candidate else row["snippet"]
            if not isinstance(text, str) or not text:
                raise ValueError("empty source text")
            if candidate:
                if sha(text.encode("utf-8")) != row["text_sha256"]:
                    raise ValueError("candidate text hash mismatch")
                start, end = row["span"]
                if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw):
                    raise ValueError("invalid candidate coordinates")
                if raw[start:end] != text:
                    raise ValueError("candidate is not its exact declared source span")
                binding = row.get("binding") or {}
                digest = binding.get("content_sha256", "").removeprefix("sha256:")
                if digest != sha(raw.encode("utf-8")):
                    raise ValueError("candidate source snapshot hash mismatch")
                scope = binding.get("scope") or {}
                if scope.get("project_id") != "local:" + sha(root.encode("utf-8")):
                    raise ValueError("candidate project binding mismatch")
                if scope.get("version") != "" or not scope.get("snapshot_id"):
                    raise ValueError("candidate version/snapshot binding missing")
                if generation is not None and scope["snapshot_id"] != generation:
                    raise ValueError("candidate generation mismatch")
            else:
                a, b = row["line_start"], row["line_end"]
                lines = raw.splitlines(keepends=True)
                if type(a) is not int or type(b) is not int or not 1 <= a <= b <= len(lines):
                    raise ValueError("invalid delivered line span")
                start, end = sum(map(len, lines[:a - 1])), sum(map(len, lines[:b]))
                if row.get("scope") != "project" or not row.get("evidence_id"):
                    raise ValueError("invalid delivered scope/reference")
                identity = row["evidence_id"]
                if identity in identities:
                    raise ValueError("duplicate delivered evidence identity")
                identities.add(identity)
                if not row.get("source_uri", "").startswith("docatlas://source/"):
                    raise ValueError("missing public source capability")
                if row.get("project_identity") != "local:" + sha(root.encode("utf-8")):
                    raise ValueError("delivered project binding mismatch")
                if row.get("authority") != "source_of_truth" or row.get("version_binding") != "unversioned":
                    raise ValueError("delivered authority/version mismatch")
                fingerprint = row.get("content_sha256")
                # The documented standalone text omits this redundant
                # projection fingerprint. It is never the raw-file hash.
                if fingerprint is not None and (not isinstance(fingerprint, str) or len(fingerprint) != 64
                        or any(c not in "0123456789abcdef" for c in fingerprint)):
                    raise ValueError("invalid delivered projection fingerprint")
            positions, cursor = [], start
            while cursor <= end - len(text):
                found = raw.find(text, cursor, end)
                if found < 0:
                    break
                positions.append((found, found + len(text)))
                cursor = found + 1
            if not positions:
                raise ValueError("source text not found in declared coordinates")
            left, right = max(a for a, _ in positions), min(b for _, b in positions)
            if left < right:
                intervals.setdefault(relative, []).append((left, right))
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            failures.append({"row": index, "error": str(exc)})
    return intervals, failures
