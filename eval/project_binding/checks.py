"""Source-bound checks for the installed current-project scenario.

Only the driver reads frozen questions/gold. No annotation is supplied to the
server, preparation, retrieval or MiniLM. This module does not execute a model.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


CASES = (
    ("B01", "What is Black's default line length?"),
    ("B02", "How does Black determine target Python versions when --target-version is not set?"),
    ("B05", "How does --force-exclude differ from --exclude for files passed explicitly to Black?"),
    ("B06", "Where does Black search for pyproject.toml, and what TCP port does blackd listen on by default?"),
    ("B08", "What guaranteed 99th-percentile formatting latency in milliseconds does Black provide?"),
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def source_docs(repo: Path) -> dict[str, str]:
    base = repo / "eval/prepared_model_comparison40/sources/black"
    expected = json.loads((repo / "eval/context_assembly/questions20.json").read_text())["source_sha256"]
    found = {}
    for path in sorted(base.rglob("*.md")):
        relative = path.relative_to(base).as_posix()
        raw = path.read_bytes()
        assert sha(raw) == expected["black/" + relative]
        found[relative] = raw.decode("utf-8")
    assert len(found) == 3
    questions = json.loads((repo / "eval/prepared_model_comparison40/questions.json").read_text())["cases"]
    by_id = {case["id"]: case for case in questions}
    for case_id, question in CASES:
        assert by_id["V40-" + case_id]["question"] == question
    return found


def contents(reply) -> tuple[dict, str]:
    assert len(reply.content) == 1 and reply.content[0].type == "text"
    assert reply.structuredContent is None and not getattr(reply, "_meta", None)
    text = reply.content[0].text
    packet = json.loads(text)
    assert isinstance(packet, dict)
    return packet, text


def decoded_rows(packet: dict) -> tuple[list[dict], str]:
    # Reuse the existing reversible wire decoder; validate every decoded byte
    # independently against the pinned source below, never against a validator.
    from docmancer.docs.application.context_assembly import decode_context
    from docmancer.docs.application.section_compression import expand_sections

    fmt = str(packet.get("context_format") or "")
    if fmt.startswith("docatlas.assembled-") or fmt == "docatlas.standalone-text.v1":
        view = decode_context(packet)
        inherited = view.get("source_context") or {}
        rows = [{**inherited, **row} for row in view.get("sources", [])]
    else:
        rows = [{**row, "path": row["path_or_url"], "text": row["snippet"],
                 "ref": row["evidence_id"]}
                for row in expand_sections(packet).get("sources", [])]
    return rows, fmt


def checked_rows(packet: dict, documents: dict[str, str], root: Path,
                 *, module_paths: tuple[str, ...] = (), authority: str = "source_of_truth"
                 ) -> tuple[list[dict], dict, str]:
    rows, fmt = decoded_rows(packet)
    identities, intervals = set(), {}
    expected_identity = "local:" + sha(str(root).encode())
    for row in rows:
        path, text = row["path"], row["text"]
        assert path in documents and isinstance(text, str) and text
        raw = documents[path]
        lines = raw.splitlines(keepends=True)
        first, last = row["line_start"], row["line_end"]
        assert type(first) is int and type(last) is int and 1 <= first <= last <= len(lines)
        begin, end = sum(map(len, lines[:first - 1])), sum(map(len, lines[:last]))
        assert text.encode() in raw[begin:end].encode()
        assert row["scope"] == ("module" if path in module_paths else "project")
        assert row["project_identity"] == expected_identity
        assert row["version_binding"] == "unversioned"
        assert row["authority"] == authority
        assert row.get("instruction_trust") == "untrusted_data"
        assert isinstance(row["ref"], str) and row["ref"] and row["ref"] not in identities
        identities.add(row["ref"])
        assert row.get("source_uri", "").startswith("docatlas://source/")
        fingerprint = row.get("content_sha256")
        # This optional projection fingerprint is not the raw file hash.
        # Raw hashes are verified in saved DB snapshots and resources/read.
        if fingerprint is not None:
            assert isinstance(fingerprint, str) and len(fingerprint) == 64
            assert all(char in "0123456789abcdef" for char in fingerprint)
        placements, cursor = [], begin
        while cursor <= end - len(text):
            at = raw.find(text, cursor, end)
            if at < 0:
                break
            placements.append((at, at + len(text)))
            cursor = at + 1
        assert placements
        # Keep the historic scorer's conservative ambiguous-placement rule.
        left, right = max(item[0] for item in placements), min(item[1] for item in placements)
        if left < right:
            intervals.setdefault(path, []).append((left, right))
    return rows, intervals, fmt


def frozen_gold(repo: Path, case_id: str, documents: dict, intervals: dict, rows: list) -> dict:
    scorer = load("binding_frozen_gold", repo / "eval/prepared_model_comparison40/evaluate.py")
    cases = json.loads((repo / "eval/prepared_model_comparison40/questions.json").read_text())["cases"]
    gold = json.loads((repo / "eval/prepared_model_comparison40/gold_spans.json").read_text())["cases"]
    full_id = "V40-" + case_id
    case = next(item for item in cases if item["id"] == full_id)
    oracle = next(item for item in gold if item["id"] == full_id)
    prepared = {"sources": {}}
    for path, content in documents.items():
        offsets = [0]
        for line in content.splitlines(keepends=True):
            offsets.append(offsets[-1] + len(line))
        prepared["sources"][path] = {"content": content, "line_offsets": offsets}
    scored = scorer._gold(case, oracle, prepared, intervals)
    assert not scored["errors"], scored
    scored.update(answerability=case["answerability"], expected_response=oracle["expected_response"],
                  negative_empty_sources=not rows if case_id == "B08" else None,
                  generated_answer_quality="NOT_TESTED")
    return scored


def check_resource(content: dict, row: dict, documents: dict[str, str], root: Path) -> None:
    assert content.get("status") in {"complete", "truncated"}, content
    if content.get("reason_code") == "end_of_source":
        assert content["status"] == "complete"
        return
    source = documents[row["path"]]
    assert content["content_sha256"] == "sha256:" + sha(source.encode())
    assert content["project_identity"] == row["project_identity"]
    assert Path(content["path"]) == root / row["path"]
    first, last = content["line_start"], content["line_end"]
    assert type(first) is int and type(last) is int and 1 <= first <= last <= len(source.splitlines())
    assert content["snippet"] == "\n".join(source.splitlines()[first - 1:last])


def source_signature(rows: list[dict]) -> list[dict]:
    # Reissued source capabilities are not source content or provenance.
    return [{key: value for key, value in row.items() if key != "source_uri"} for row in rows]
