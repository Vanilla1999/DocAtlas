"""Independent raw-source and state receipts, reused by public scenarios."""
from __future__ import annotations

from contextlib import closing, contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import signal
import sqlite3


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def ledger(path, operation, status, **fields):
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(dict(at_utc=datetime.now(timezone.utc).isoformat(),
                                    operation=operation, status=status, **fields)) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


@contextmanager
def deadline(seconds):
    """Linux/main-thread per-call ceiling; outer coordinator must also bound wall."""
    def expired(signum, frame):
        raise TimeoutError(f"frozen deadline {seconds}s")
    previous = signal.signal(signal.SIGALRM, expired)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def files(root):
    return {p.relative_to(root).as_posix(): sha(p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file()}


def database(path):
    """Read-only logical state equality, not an expected implementation snapshot."""
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as db:
        names = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        return {name: sha(repr(sorted(db.execute('SELECT * FROM "' + name.replace('"', '""') + '"')
                                      .fetchall(), key=repr)).encode()) for (name,) in names}


def snapshots(inventory, root, documents):
    with closing(sqlite3.connect(Path(inventory["storage_path"]).resolve().as_uri() + "?mode=ro", uri=True)) as db:
        rows = db.execute("SELECT source, content, metadata_json FROM generation_sources WHERE generation_id=?",
                          (inventory["generation_id"],)).fetchall()
    result = []
    for source, content, metadata in rows:
        relative = Path(source).relative_to(root).as_posix()
        digest = sha(content.encode())
        if relative not in documents or content != documents[relative]:
            raise ValueError("committed source differs from independent pinned bytes")
        if json.loads(metadata).get("project_doc_content_hash") != "sha256:" + digest:
            raise ValueError("committed raw hash mismatch")
        result.append(dict(path=relative, content_sha256=digest, matches_pinned_source=True))
    if {row["path"] for row in result} != set(documents):
        raise ValueError("published source membership mismatch")
    return result


def relative_path(value, root):
    if not isinstance(value, str) or "://" in value or "\\" in value:
        return None
    path = Path(value)
    if ".." in path.parts:
        return None
    try:
        return path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
    except ValueError:
        return None


def integrity(payload, root, documents, module_paths=()):
    """Check actual public sources against independent bytes, not product validators.

    content_sha256 is a projection fingerprint: shape only, not a raw-file hash.
    Raw source hashes are independently checked in snapshots/resources/read_next.
    """
    errors, rows, identities = [], [], set()
    expected_identity = "local:" + sha(str(root).encode())
    if not isinstance(payload, dict) or not isinstance(payload.get("sources", []), list):
        return {"errors": ["invalid_public_payload"], "rows": []}
    for index, row in enumerate(payload.get("sources") or []):
        issues = []
        relative = relative_path(row.get("path_or_url"), root)
        text = documents.get(relative)
        start, end, snippet = row.get("line_start"), row.get("line_end"), row.get("snippet")
        if text is None:
            issues.append("foreign_source")
        elif not (type(start) is int and type(end) is int and 1 <= start <= end <= len(text.splitlines())):
            issues.append("invalid_line_span")
        elif not isinstance(snippet, str) or not snippet or snippet.encode() not in "".join(
                text.splitlines(keepends=True)[start - 1:end]).encode():
            issues.append("not_exact_raw_span")
        expected_scope = "module" if relative in module_paths else "project"
        if row.get("scope") != expected_scope:
            issues.append("wrong_scope")
        if row.get("version_binding") != "unversioned":
            issues.append("wrong_version")
        if row.get("authority") != "source_of_truth" or row.get("project_identity") != expected_identity:
            issues.append("wrong_source_identity_or_authority")
        fingerprint = row.get("content_sha256")
        if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
            issues.append("invalid_projection_fingerprint")
        identity = row.get("evidence_id")
        if not isinstance(identity, str) or not identity or identity in identities:
            issues.append("duplicate_or_missing_evidence_id")
        identities.add(identity)
        rows.append(dict(index=index, path=relative, raw_sha256=sha(text.encode()) if text is not None else None,
                         errors=issues))
        errors.extend(f"source[{index}]:{issue}" for issue in issues)
    for target in payload.get("read_next") or []:
        relative = relative_path(target.get("path"), root)
        text = documents.get(relative)
        if text is None or target.get("snapshot_sha256") != "sha256:" + sha(text.encode()):
            errors.append("invalid_continuation_raw_hash_or_membership")
        elif not (type(target.get("line_start")) is int and type(target.get("line_end")) is int
                  and 1 <= target["line_start"] <= target["line_end"] <= len(text.splitlines())):
            errors.append("invalid_continuation_span")
        if target.get("project_identity") != expected_identity:
            errors.append("invalid_continuation_identity")
    for key in ("answer_supported", "answer_available", "edit_ready"):
        if payload.get(key) is True:
            errors.append("unexpected_authority:" + key)
    return dict(errors=errors, rows=rows)


def stable_packet(payload):
    """Exclude only reissued capability bytes and their dependent estimate."""
    result = deepcopy(payload)
    result.pop("estimated_tokens", None)
    for key in ("sources", "read_next"):
        for row in result.get(key) or []:
            row.pop("source_uri", None)
    return result


def pack(payload, tokenizer, cap):
    """Whole-source ranked prefix; no crop, oracle, question or semantic score."""
    evidence = []
    for row in payload.get("sources") or []:
        candidate = evidence + [row]
        wire = json.dumps(candidate, ensure_ascii=False, sort_keys=True)
        if len(tokenizer.encode(wire, disallowed_special=())) > cap:
            break
        evidence = candidate
    wire = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    return dict(sources=evidence, tokens=len(tokenizer.encode(wire, disallowed_special=())),
                utf8_bytes=len(wire.encode()), sha256=sha(wire.encode()),
                policy="whole-source input-rank prefix including full attribution", ceiling=cap)
