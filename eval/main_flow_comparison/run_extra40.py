"""Additional 40-question retrieval evaluation through real public MCP and SQLite.

The report checks independent source-bound factual coverage. Missing facts
are measured, not converted into a passing answer certification. Not a unit test.
"""
from __future__ import annotations

from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from eval.evidence_quality_v2.runtime import index_project, isolated_service
from scripts import run_project_docs_self_host_gate as runner

CORPUS_SHA = "31da2449b89b3edc72f6f463a84144d256105a77f99bfe5c7bdeab9cdd3c1d00"
OLD_QUESTIONS_SHA = "2b88e653b4726747d4ee55682d159744bc1b7dcfc8ac525ee830a688ec401f67"


def _covered(corpus, ranges, fact):
    merged = []
    for a, b in sorted(ranges):
        if merged and (a <= merged[-1][1] or not corpus[merged[-1][1]:a].strip()):
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return any(a <= fact[0] and b >= fact[1] for a, b in merged)


def main():
    here = Path(__file__).resolve().parent
    original = (here / "questions.json").read_bytes()
    source_bytes = (here / "corpus.md").read_bytes()
    extra = (here / "questions_extra40.json").read_bytes()
    assert sha256(original).hexdigest() == OLD_QUESTIONS_SHA
    assert sha256(source_bytes).hexdigest() == CORPUS_SHA
    corpus = source_bytes.decode("utf-8")
    cases = json.loads(extra)
    assert len(cases) == 40
    questions = [q for q, _ in cases]
    assert len(set(questions)) == 40
    assert not set(questions) & {q["question"] for q in json.loads(original)}
    assert all(f and all(type(a) is int and type(b) is int and
                         0 <= a < b <= len(corpus) for a, b in f)
               for _, f in cases)
    destination = Path(os.environ["EXTRA40_ARTIFACT_DIR"]).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / "extra40-results.json"
    record = {
        "boundary": "real public Docs MCP dispatcher / SQLite; not Grounded or installed client",
        "corpus_sha256": CORPUS_SHA,
        "original_questions_sha256": OLD_QUESTIONS_SHA,
        "new_questions_sha256": sha256(extra).hexdigest(),
        "product_calls": {"prepare_docs": 1, "get_docs_context": 0},
        "results": [],
    }

    def save():
        report_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

    with TemporaryDirectory(prefix="docatlas-extra40-") as tmp:
        project = (Path(tmp) / "project").resolve()
        project.mkdir(mode=0o700)
        (project / "README.md").write_bytes(source_bytes)
        catalog = project / "docatlas.project-docs.yaml"
        catalog.write_text(json.dumps({
            "schema_version": 1, "code_files": [], "documents": [{
                "path": "README.md", "role": "overview", "scope": "project",
                "description": "DocAtlas main-flow logging and evaluation documentation",
                "authority": "source_of_truth",
            }],
        }), encoding="utf-8")
        catalog_before = catalog.read_bytes()
        project_id = "local:" + sha256(str(project).encode("utf-8")).hexdigest()
        line_offsets = [0]
        for line in corpus.splitlines(keepends=True):
            line_offsets.append(line_offsets[-1] + len(line))
        with isolated_service(Path(tmp) / "state") as (service, config):
            prepared = index_project(service, config, project)
            generation = prepared["generation_id"]
            policy = service._cold.member_storage_policy
            with closing(policy.connect()) as connection:
                stored = connection.execute(
                    "SELECT source, content, content_hash, source_identity "
                    "FROM generation_sources WHERE generation_id = ?", (generation,),
                ).fetchall()
            assert [tuple(row)[:3] for row in stored] == [
                (str(project / "README.md"), corpus, CORPUS_SHA),
            ]
            for idx, (question, facts) in enumerate(cases, 11):
                started = perf_counter()
                row = {"id": idx, "question": question, "required_facts": [
                    {"start": a, "end": b, "quote": corpus[a:b]} for a, b in facts,
                ]}
                try:
                    payload, snapshot = runner._call_with_snapshot({
                        "question": question, "project_path": str(project), "scope": "project",
                    }, service)
                    row["elapsed_ms"] = round(1000 * (perf_counter() - started), 2)
                    row["payload"] = payload
                    row["validation_snapshot"] = snapshot
                    ranges, errors = [], []
                    sources = payload.get("sources") or []
                    for item in sources:
                        eid = item.get("evidence_id")
                        bound = (snapshot.get(eid) or {})
                        src = bound.get("source") or {}
                        ref = src.get("_reference_evidence") or {}
                        identity = ref.get("source") or {}
                        scope = identity.get("scope") or {}
                        if not (
                            bound.get("projected_source") == item
                            and item.get("path_or_url") == "README.md"
                            and item.get("project_identity") == project_id
                            and item.get("scope") == "project"
                            and item.get("authority") == "source_of_truth"
                            and item.get("version_binding") == "unversioned"
                            and ref.get("raw_document") == corpus
                            and identity.get("canonical_path") == "README.md"
                            and identity.get("content_sha256") == CORPUS_SHA
                            and identity.get("document_id") == stored[0]["source_identity"]
                            and scope.get("project_id") == project_id
                            and scope.get("snapshot_id") == generation
                            and scope.get("version") == ""
                        ):
                            errors.append("source_identity:" + str(eid))
                            continue
                        a, b, reftext = (ref.get(k) for k in ("char_start", "char_end", "text"))
                        if not (type(a) is int and type(b) is int and
                                0 <= a < b <= len(corpus) and reftext == corpus[a:b]):
                            errors.append("source_reference:" + str(eid))
                            continue
                        snippet = item.get("snippet", "").strip()
                        if not snippet or reftext.count(snippet) != 1:
                            errors.append("source_literal:" + str(eid))
                            continue
                        first, last = a + reftext.index(snippet), a + reftext.index(snippet) + len(snippet)
                        line_first, line_last = item.get("line_start"), item.get("line_end")
                        if not (type(line_first) is int and type(line_last) is int and
                                1 <= line_first <= line_last < len(line_offsets) and
                                line_offsets[line_first - 1] <= first and last <= line_offsets[line_last]):
                            errors.append("source_lines:" + str(eid))
                            continue
                        ranges.append((first, last))
                    missing = [corpus[a:b] for a, b in facts if not _covered(corpus, ranges, (a, b))]
                    row["audit"] = {
                        "status": payload.get("status"),
                        "support_status": payload.get("support_status"),
                        "answer_supported": payload.get("answer_supported"),
                        "source_count": len(sources),
                        "valid_source_ranges": ranges,
                        "errors": errors,
                        "missing_facts": missing,
                        "facts_delivered": not errors and not missing,
                    }
                except Exception as exc:
                    row["elapsed_ms"] = round(1000 * (perf_counter() - started), 2)
                    row["audit"] = {"execution_error": f"{type(exc).__name__}: {exc}",
                                    "facts_delivered": False}
                record["results"].append(row)
                record["product_calls"]["get_docs_context"] += 1
                if idx % 10 == 0:
                    save()
            assert policy.generation() == generation
            with closing(policy.connect()) as connection:
                now = connection.execute(
                    "SELECT source, content, content_hash, source_identity "
                    "FROM generation_sources WHERE generation_id = ?", (generation,),
                ).fetchall()
            assert [tuple(x) for x in now] == [tuple(x) for x in stored]
        assert (project / "README.md").read_bytes() == source_bytes
        assert catalog.read_bytes() == catalog_before
    delivered = sum(bool(row["audit"]["facts_delivered"]) for row in record["results"])
    failures = [row["id"] for row in record["results"] if not row["audit"]["facts_delivered"]]
    record["summary"] = {
        "questions": len(cases), "full_facts": delivered, "failed_ids": failures,
        "runtime_errors": sum("execution_error" in row["audit"] for row in record["results"]),
        "source_integrity_errors": sum(bool(row["audit"].get("errors")) for row in record["results"]),
    }
    save()
    print("Extra40 public MCP factual source delivery:", json.dumps(record["summary"]))
    assert len(record["results"]) == 40
    assert record["summary"]["runtime_errors"] == 0
    assert record["summary"]["source_integrity_errors"] == 0


if __name__ == "__main__":
    main()
