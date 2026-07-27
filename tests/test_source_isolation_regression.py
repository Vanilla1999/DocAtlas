from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from docmancer.core.config import DocmancerConfig
from docmancer.core.models import RetrievedChunk
from docmancer.docs.application.docs_job_service import DocsJobTracker
from docmancer.docs.application.evidence_selection import SelectionDecision
from docmancer.docs.application.model_visible_projection import (
    estimate_projection_tokens,
    project_docs_answer,
    validate_model_visible_projection,
)
from docmancer.docs.registry import LibraryRegistry
from docmancer.docs.service import LibraryDocsService


class RecordingAgent:
    def __init__(self, chunks=None):
        self.chunks = chunks or []
        self.add_calls: list[str] = []
        self.add_kwargs: list[dict] = []
        self.query_calls: list[str] = []
        self.config = None

    def add(self, docs_url: str, recreate: bool = False, **kwargs) -> int:
        self.add_calls.append(docs_url)
        self.add_kwargs.append(kwargs)
        if self.config is not None:
            marker = Path(self.config.index.extracted_dir) / "chunk.md"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("indexed chunk", encoding="utf-8")
        return 1

    def query(self, text: str, limit=None, budget=None, expand=None):
        self.query_calls.append(text)
        return self.chunks


def _service(tmp_path, monkeypatch, agent: RecordingAgent | None = None) -> LibraryDocsService:
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    agent = agent or RecordingAgent()
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")

    def agent_factory(**kwargs):
        agent.config = kwargs.get("config")
        return agent

    return LibraryDocsService(
        config=config,
        registry=LibraryRegistry(config.index.db_path),
        agent=agent,
        agent_factory=agent_factory,
        job_tracker=DocsJobTracker(),
    )


def _register(service: LibraryDocsService, *, library: str, ecosystem: str | None = None, version: str | None = None, docs_url: str, source_type: str | None = "api", indexed: bool = True):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library=library,
        ecosystem=ecosystem,
        version=version,
        source_type=source_type,
        docs_url=docs_url,
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    if indexed:
        config = service._index_config_for(record)
        marker = Path(config.index.extracted_dir) / "chunk.md"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("indexed chunk", encoding="utf-8")
    return record


def _chunk(text: str, source: str, metadata: dict):
    return RetrievedChunk(source=source, chunk_index=0, text=text, score=1.0, metadata=metadata)


def test_click_query_does_not_return_fastapi_or_flutter(tmp_path, monkeypatch):
    agent = RecordingAgent(
        [
            _chunk(
                "Click command docs.",
                "https://click.palletsprojects.com/en/8.1.x/commands/",
                {"library_id": "python:click@8.1.7:api", "canonical_id": "python:click@8.1.7:api", "ecosystem": "python", "version": "8.1.7"},
            ),
            _chunk("FastAPI docs.", "https://fastapi.tiangolo.com/tutorial/", {"library_id": "python:fastapi@0.110.0:api"}),
            _chunk("Flutter docs.", "https://api.flutter.dev/widgets/widgets-library.html", {"library_id": "flutter:flutter-api@stable:api"}),
            _chunk("Project README.", "/repo/README.md", {"project_path": "/repo"}),
        ]
    )
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/")

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands")

    assert result.status == "success"
    assert [chunk.content for chunk in result.results] == ["Click command docs."]


def test_python_direct_text_exact_sources_override_broad_docset_root(tmp_path, monkeypatch):
    base64_url = "https://docs.python.org/3.13/library/base64.html"
    zlib_url = "https://docs.python.org/3.13/library/zlib.html"
    library_id = "python:python@3.13:api"
    base64_chunk = _chunk(
        "Python 3.13 base64.b64encode encodes bytes with the Base64 alphabet.",
        base64_url,
        {
            "stable_chunk_id": "python-3.13-base64",
            "library_id": library_id,
            "canonical_id": library_id,
            "ecosystem": "python",
            "version": "3.13",
            "source_type": "api",
            "docset_root": "https://docs.python.org",
        },
    )
    zlib_chunk = _chunk(
        "Python 3.13 zlib.compress returns compressed bytes for input data.",
        zlib_url,
        {
            "stable_chunk_id": "python-3.13-zlib",
            "library_id": library_id,
            "canonical_id": library_id,
            "ecosystem": "python",
            "version": "3.13",
            "source_type": "api",
            "docset_root": "https://docs.python.org",
        },
    )
    agent = RecordingAgent([base64_chunk, zlib_chunk])
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        docs_url=base64_url,
        target_spec={"seed_urls": [base64_url, zlib_url]},
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    config = service._index_config_for(record)
    marker = Path(config.index.extracted_dir) / "chunk.md"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("indexed chunk", encoding="utf-8")

    base64_result = service.get_docs(
        "python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        topic="base64 b64encode",
    )
    agent.chunks = [zlib_chunk]
    zlib_result = service.get_docs(
        "python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        topic="zlib compress",
    )
    agent.chunks = [base64_chunk, zlib_chunk]
    repeated_base64_result = service.get_docs(
        "python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        topic="base64 b64encode",
    )

    assert base64_result.status == zlib_result.status == "success"
    assert base64_result.diagnostics["retrieval"]["post_guard"]["accepted"] == 2
    assert isinstance(base64_result.selection_decision, SelectionDecision)
    assert isinstance(zlib_result.selection_decision, SelectionDecision)
    assert base64_result.selected_evidence_ids == ["python-3.13-base64"]
    assert zlib_result.selected_evidence_ids == ["python-3.13-zlib"]
    assert base64_result.decision_hash
    assert zlib_result.decision_hash
    assert repeated_base64_result.decision_hash == base64_result.decision_hash

    info = service.resolve_library("python", ecosystem="python", version="3.13", source_type="api")
    expected_roots = {base64_url, zlib_url}
    exact_metadata = {
        "library_id": library_id,
        "canonical_id": library_id,
        "ecosystem": "python",
        "version": "3.13",
        "source_type": "api",
        "docset_root": "https://docs.python.org",
    }
    assert service.library_docs._library_chunk_rejection_reason(
        _chunk("Base64 docs.", base64_url + "/", exact_metadata),
        info,
        {library_id},
        expected_roots,
    ) is None
    fail_closed_cases = [
        (base64_url + "?download=1", exact_metadata, "wrong_docset_root"),
        (base64_url + "#functions", exact_metadata, "wrong_docset_root"),
        (base64_url + ".attacker", exact_metadata, "wrong_docset_root"),
        ("https://docs.python.org.attacker/3.13/library/base64.html", exact_metadata, "wrong_docset_root"),
        ("", exact_metadata, "wrong_docset_root"),
        (base64_url, {**exact_metadata, "docset_root": "https://attacker.invalid"}, "wrong_docset_root"),
        (base64_url, {**exact_metadata, "url": "https://attacker.invalid/base64.html"}, "wrong_docset_root"),
        (base64_url, {**exact_metadata, "version": "3.12"}, "wrong_version"),
        (base64_url, {**exact_metadata, "version": {"malformed": True}}, "wrong_version"),
        (base64_url, {"docset_root": "https://docs.python.org"}, "missing_library_metadata"),
        (base64_url, {**exact_metadata, "library_id": "python:other@3.13:api"}, "wrong_library_id"),
    ]
    for source, metadata, expected_reason in fail_closed_cases:
        chunk = _chunk("Untrusted docs.", source, metadata)
        assert service.library_docs._library_chunk_rejection_reason(
            chunk,
            info,
            {library_id},
            expected_roots,
        ) == expected_reason


ZLIB_EVIDENCE_QUESTION = (
    "How does Python 3.13 zlib.Decompress.decompress(data, max_length) limit returned output, "
    "and what do eof, unused_data, and unconsumed_tail mean? Return source-backed evidence only."
)

ZLIB_EVIDENCE_PARAPHRASES = (
    (
        "How does Python 3.13 zlib.Decompress.decompress(data, max_length) limit returned output? "
        "Explain eof plus unused_data and unconsumed_tail."
    ),
    (
        "For Python 3.13 zlib.Decompress.decompress(data, max_length), describe these "
        "Decompress attributes: eof, unused_data, and unconsumed_tail."
    ),
    (
        "In Python 3.13, explain max_length for zlib.Decompress.decompress(data, max_length); "
        "give the meaning of eof / unused_data / unconsumed_tail."
    ),
)

ZLIB_DELIMITER_PROSE_CONTROLS = (
    (
        "For Python 3.13 zlib.Decompress.decompress(data, max_length), explain output and data "
        "for this workflow.",
        {"output", "data"},
    ),
    (
        "For Python 3.13 zlib.Decompress.decompress(data, max_length), describe these fields: "
        "output, data.",
        {"output", "data"},
    ),
    (
        "For Python 3.13 zlib.Decompress.decompress(data, max_length), give the semantics of "
        "bytes / output.",
        {"bytes", "output"},
    ),
)


def _oversized_zlib_source() -> str:
    return "\n".join([
        "zlib — Compression compatible with gzip",
        "==========================================",
        "",
        ".. module:: zlib",
        "",
        *("General compression background that does not describe the requested API." for _ in range(900)),
        "",
        ".. attribute:: Decompress.unused_data",
        "",
        "   A bytes object which contains any bytes past the end of the compressed data.",
        "",
        ".. attribute:: Decompress.unconsumed_tail",
        "",
        "   A bytes object that contains compressed input not consumed because output was limited.",
        "",
        ".. attribute:: Decompress.eof",
        "",
        "   A boolean indicating whether the end of the compressed data stream has been reached.",
        "",
        ".. method:: Decompress.decompress(data, max_length=0)",
        "",
        "   If max_length is non-zero, the returned output is no longer than max_length.",
    ])


def _zlib_fixture_service(tmp_path, monkeypatch) -> LibraryDocsService:
    source_url = "https://docs.python.org/3.13/_sources/library/zlib.rst.txt"
    library_id = "python:python@3.13:api"
    chunk = _chunk(
        _oversized_zlib_source(),
        source_url,
        {
            "stable_chunk_id": "python-3.13-zlib-source",
            "library_id": library_id,
            "canonical_id": library_id,
            "ecosystem": "python",
            "version": "3.13",
            "source_type": "api",
            "docset_root": "https://docs.python.org",
        },
    )
    service = _service(tmp_path, monkeypatch, RecordingAgent([chunk]))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        docs_url=source_url,
        target_spec={"seed_urls": [source_url]},
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    marker = Path(service._index_config_for(record).index.extracted_dir) / "chunk.md"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("indexed chunk", encoding="utf-8")
    return service


def _public_library_projection(question: str, result, *, max_tokens: int = 800):
    context_pack = [
        {
            "source": chunk.source,
            "content": chunk.content,
            "version": result.resolved_version,
            "docs_exactness": "exact",
            "stable_chunk_id": chunk.metadata.get("stable_chunk_id"),
            "parent_logical_id": chunk.metadata.get("parent_logical_id") or chunk.source,
            "display_content_hash": hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
            "authority": "official",
        }
        for chunk in result.results
    ]
    return project_docs_answer(
        question=question,
        retrieval={
            "status": result.status,
            "context_available": bool(result.results),
            "answer_available": bool(result.results),
            "context_pack": context_pack,
            "selection_profile": "library_docs_answer",
            "selection_decision": result.selection_decision,
            "requested_version": "3.13",
            "docs_exactness": "exact",
        },
        canonical_selection=result.selection_decision,
        max_tokens=max_tokens,
    )[0]


def test_exact_python_source_derives_bounded_canonical_zlib_evidence(tmp_path, monkeypatch):
    service = _zlib_fixture_service(tmp_path, monkeypatch)

    result = service.get_docs(
        "python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        topic=ZLIB_EVIDENCE_QUESTION,
    )
    projection = _public_library_projection(ZLIB_EVIDENCE_QUESTION, result)

    assert isinstance(result.selection_decision, SelectionDecision)
    assert result.answer_supported is True
    assert result.answer_available is True
    assert result.support_status == "supported"
    assert result.mandatory_coverage == 1.0
    assert result.missing_requirement_ids == []
    assert result.selected_evidence_ids
    assert result.decision_hash
    assert {requirement.value for requirement in result.requirements} >= {
        "zlib.Decompress.decompress",
        "max_length",
        "eof",
        "unused_data",
        "unconsumed_tail",
    }
    evidence = "\n".join(chunk.content for chunk in result.results)
    assert "returned output is no longer than max_length" in evidence
    assert "end of the compressed data stream has been reached" in evidence
    assert "bytes past the end of the compressed data" in evidence
    assert "compressed input not consumed because output was limited" in evidence
    assert len(evidence.encode("utf-8")) <= 680 * 4
    assert projection["status"] == "ok"
    assert projection["answer_supported"] is True
    assert projection["selected_evidence_ids"] == result.selected_evidence_ids
    assert projection["decision_hash"] == result.decision_hash

    control_question = "How does Python 3.13 zlib.Decompress.nonexistent_api(data) work?"
    control = service.get_docs(
        "python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        topic=control_question,
    )
    control_projection = _public_library_projection(control_question, control, max_tokens=256)
    assert control_projection["status"] == "insufficient_evidence"
    assert control_projection["support_status"] == "insufficient_evidence"
    assert control_projection["answer_supported"] is False
    assert control_projection["answer_available"] is False
    assert control_projection["selected_evidence_ids"] == []
    assert control_projection["decision_hash"] is None
    assert "support_envelope" not in control_projection
    assert "sources" not in control_projection
    assert control_projection["estimated_tokens"] == estimate_projection_tokens(control_projection)
    assert validate_model_visible_projection(
        control_projection,
        snapshot={},
        max_tokens=256,
    ) == []


@pytest.mark.parametrize("question", ZLIB_EVIDENCE_PARAPHRASES)
def test_python_semantic_list_paraphrases_require_all_named_zlib_attributes(
    tmp_path,
    monkeypatch,
    question,
):
    service = _zlib_fixture_service(tmp_path, monkeypatch)

    result = service.get_docs(
        "python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        topic=question,
    )
    repeated = service.get_docs(
        "python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        topic=question,
    )
    projection = _public_library_projection(question, result)

    requirement_values = {requirement.value for requirement in result.requirements}
    assert requirement_values >= {
        "zlib.Decompress.decompress",
        "max_length",
        "eof",
        "unused_data",
        "unconsumed_tail",
    }
    assert result.answer_supported is True
    assert result.answer_available is True
    assert result.support_status == "supported"
    assert result.mandatory_coverage == 1.0
    assert result.missing_requirement_ids == []
    assert result.selected_evidence_ids
    assert result.decision_hash
    assert repeated.selected_evidence_ids == result.selected_evidence_ids
    assert repeated.decision_hash == result.decision_hash
    assert result.library_id == "python:python@3.13:api"
    assert result.resolved_version == "3.13"
    assert {chunk.source for chunk in result.results} == {
        "https://docs.python.org/3.13/_sources/library/zlib.rst.txt"
    }
    assert projection["status"] == "ok"
    assert projection["selected_evidence_ids"] == result.selected_evidence_ids
    assert projection["decision_hash"] == result.decision_hash


@pytest.mark.parametrize(("question", "ordinary_words"), ZLIB_DELIMITER_PROSE_CONTROLS)
def test_delimiter_like_prose_does_not_promote_ordinary_words_or_change_canonical_support(
    tmp_path,
    monkeypatch,
    question,
    ordinary_words,
):
    service = _zlib_fixture_service(tmp_path, monkeypatch)
    baseline_question = (
        "For Python 3.13 zlib.Decompress.decompress(data, max_length), explain this workflow."
    )

    result = service.get_docs(
        "python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        topic=question,
    )
    baseline = service.get_docs(
        "python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        topic=baseline_question,
    )
    projection = _public_library_projection(question, result)

    requirement_values = {
        requirement.value.casefold() for requirement in (result.requirements or [])
    }
    assert requirement_values.isdisjoint(ordinary_words)
    assert result.answer_supported is False
    assert result.answer_available is False
    assert result.selected_evidence_ids == []
    assert result.decision_hash is None
    assert result.reason_code == "unqualified_explicit_query_list"
    assert baseline.answer_supported is True
    assert baseline.answer_available is True
    assert baseline.selected_evidence_ids
    assert baseline.decision_hash
    assert projection["status"] == "insufficient_evidence"
    assert projection["selected_evidence_ids"] == []
    assert projection["decision_hash"] is None
    assert "sources" not in projection


def test_unrelated_eof_prose_does_not_create_a_typed_requirement_or_support(
    tmp_path,
    monkeypatch,
):
    service = _zlib_fixture_service(tmp_path, monkeypatch)
    question = (
        "The diagnostic log happened to mention eof as background. How does Python 3.13 "
        "zlib.Decompress.nonexistent_api(data) work?"
    )

    result = service.get_docs(
        "python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        topic=question,
    )
    projection = _public_library_projection(question, result, max_tokens=256)

    assert not result.requirements or "eof" not in {
        requirement.value.casefold() for requirement in result.requirements
    }
    assert result.answer_supported is False
    assert result.answer_available is False
    assert result.selected_evidence_ids == []
    assert result.decision_hash is None
    assert projection["status"] == "insufficient_evidence"
    assert projection["selected_evidence_ids"] == []
    assert projection["decision_hash"] is None
    assert "sources" not in projection


def _python_direct_text_result(
    tmp_path,
    monkeypatch,
    metadata: dict,
    *,
    chunk_source: str = "https://docs.python.org/3.13/library/base64.html",
):
    source_url = "https://docs.python.org/3.13/library/base64.html"
    chunk = _chunk(
        "Python 3.13 base64.b64encode encodes bytes with the Base64 alphabet.",
        chunk_source,
        {"stable_chunk_id": "probe", **metadata},
    )
    service = _service(tmp_path, monkeypatch, RecordingAgent([chunk]))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = service.registry.upsert(
        library="python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        docs_url=source_url,
        target_spec={"seed_urls": [source_url]},
        now=now,
        status="available",
        last_refreshed_at=now,
    )
    marker = Path(service._index_config_for(record).index.extracted_dir) / "chunk.md"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("indexed chunk", encoding="utf-8")
    return service.get_docs(
        "python",
        ecosystem="python",
        version="3.13",
        source_type="api",
        topic="base64 b64encode",
    )


def test_python_direct_text_broad_root_accepts_complete_resolved_version_identity(tmp_path, monkeypatch):
    library_id = "python:python@3.13:api"
    metadata = {
        "library_id": library_id,
        "canonical_id": library_id,
        "ecosystem": "python",
        "resolved_version": "3.13",
        "source_type": "api",
        "docset_root": "https://docs.python.org",
    }
    result = _python_direct_text_result(tmp_path / "first", monkeypatch, metadata)
    repeated = _python_direct_text_result(tmp_path / "repeated", monkeypatch, metadata)

    assert result.status == "success"
    assert isinstance(result.selection_decision, SelectionDecision)
    assert getattr(SelectionDecision, "__dataclass_params__").frozen is True
    assert result.selected_evidence_ids == ["probe"]
    assert result.decision_hash
    assert repeated.decision_hash == result.decision_hash


@pytest.mark.parametrize("omitted_field", ["canonical_id", "ecosystem", "version", "source_type"])
def test_python_direct_text_broad_root_requires_complete_identity(tmp_path, monkeypatch, omitted_field):
    library_id = "python:python@3.13:api"
    complete_metadata = {
        "library_id": library_id,
        "canonical_id": library_id,
        "ecosystem": "python",
        "version": "3.13",
        "source_type": "api",
        "docset_root": "https://docs.python.org",
    }
    metadata = {key: value for key, value in complete_metadata.items() if key != omitted_field}
    result = _python_direct_text_result(tmp_path, monkeypatch, metadata)
    assert result.status == "empty_library_index"
    assert result.selection_decision is None
    assert result.selected_evidence_ids == []
    assert result.decision_hash is None


@pytest.mark.parametrize("conflicting_alias", ["source_url", "url"])
def test_python_direct_text_broad_root_rejects_conflicting_url_aliases(tmp_path, monkeypatch, conflicting_alias):
    source_url = "https://docs.python.org/3.13/library/base64.html"
    library_id = "python:python@3.13:api"
    complete_metadata = {
        "library_id": library_id,
        "canonical_id": library_id,
        "ecosystem": "python",
        "version": "3.13",
        "source_type": "api",
        "docset_root": "https://docs.python.org",
    }
    exact_alias = "url" if conflicting_alias == "source_url" else "source_url"
    metadata = {
        **complete_metadata,
        exact_alias: source_url,
        conflicting_alias: "https://attacker.invalid/base64.html",
    }
    result = _python_direct_text_result(tmp_path, monkeypatch, metadata)
    assert result.status == "empty_library_index"
    assert result.selection_decision is None
    assert result.selected_evidence_ids == []
    assert result.decision_hash is None


@pytest.mark.parametrize(
    "invalid_case",
    [
        "wrong_version",
        "malformed_version",
        "wrong_authority",
        "prefix_confusable",
        "query",
        "fragment",
        "absent_source",
        "metadata_only_root",
        "unrelated_same_authority",
        "cross_docset",
    ],
)
def test_python_direct_text_broad_root_negative_matrix_has_no_selection_decision(tmp_path, monkeypatch, invalid_case):
    source_url = "https://docs.python.org/3.13/library/base64.html"
    library_id = "python:python@3.13:api"
    metadata: dict = {
        "library_id": library_id,
        "canonical_id": library_id,
        "ecosystem": "python",
        "version": "3.13",
        "source_type": "api",
        "docset_root": "https://docs.python.org",
    }
    chunk_source = source_url
    if invalid_case == "wrong_version":
        metadata["version"] = "3.12"
    elif invalid_case == "malformed_version":
        metadata["version"] = {"malformed": True}
    elif invalid_case == "wrong_authority":
        chunk_source = "https://attacker.invalid/3.13/library/base64.html"
    elif invalid_case == "prefix_confusable":
        chunk_source = source_url + ".attacker"
    elif invalid_case == "query":
        chunk_source = source_url + "?download=1"
    elif invalid_case == "fragment":
        chunk_source = source_url + "#functions"
    elif invalid_case == "absent_source":
        chunk_source = ""
    elif invalid_case == "metadata_only_root":
        metadata = {"docset_root": "https://docs.python.org"}
        chunk_source = ""
    elif invalid_case == "unrelated_same_authority":
        chunk_source = "https://docs.python.org/3.13/library/asyncio.html"
    elif invalid_case == "cross_docset":
        metadata["library_id"] = metadata["canonical_id"] = "python:other@3.13:api"

    result = _python_direct_text_result(tmp_path, monkeypatch, metadata, chunk_source=chunk_source)
    assert result.status == "empty_library_index"
    assert result.selection_decision is None
    assert result.selected_evidence_ids == []
    assert result.decision_hash is None


def test_flutter_bloc_query_does_not_return_unrelated_project_docs(tmp_path, monkeypatch):
    agent = RecordingAgent(
        [
            _chunk(
                "BlocBuilder docs.",
                "https://pub.dev/documentation/flutter_bloc/9.1.1/flutter_bloc/BlocBuilder-class.html",
                {"library_id": "pub:flutter_bloc@9.1.1:api", "canonical_id": "pub:flutter_bloc@9.1.1:api", "ecosystem": "pub", "version": "9.1.1"},
            ),
            _chunk("Smart glasses architecture.", "/workspace/fixtures/smart_glasses/ARCHITECTURE.md", {"project_path": "/workspace/fixtures/smart_glasses"}),
        ]
    )
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="flutter_bloc", ecosystem="pub", version="9.1.1", docs_url="https://pub.dev/documentation/flutter_bloc/9.1.1/")

    result = service.get_docs("flutter_bloc", ecosystem="pub", version="9.1.1", source_type="api", topic="BlocBuilder")

    assert [chunk.content for chunk in result.results] == ["BlocBuilder docs."]
    assert all("smart_glasses" not in (chunk.source or "") for chunk in result.results)


def test_empty_library_index_returns_controlled_error(tmp_path, monkeypatch):
    agent = RecordingAgent([_chunk("Project README.", "/repo/README.md", {"project_path": "/repo"})])
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/", indexed=False)

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands")

    assert result.status == "empty_library_index"
    assert result.decision == "stop"
    assert result.diagnostics["reason_code"] == "empty_index"
    assert result.next_actions == ["Call refresh_library_docs to ingest this library's docs."]
    assert result.results == []
    assert agent.query_calls == []


def test_project_query_then_library_query_uses_per_library_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    default_agent = RecordingAgent([_chunk("Project README.", "/repo/README.md", {"project_path": "/repo"})])
    library_agent = RecordingAgent(
        [_chunk("Click command docs.", "https://click.palletsprojects.com/en/8.1.x/commands/", {"library_id": "python:click@8.1.7:api", "canonical_id": "python:click@8.1.7:api", "ecosystem": "python", "version": "8.1.7"})]
    )
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "docmancer.db")
    config.index.extracted_dir = str(tmp_path / "extracted")

    def agent_factory(**kwargs):
        library_agent.config = kwargs.get("config")
        return library_agent

    service = LibraryDocsService(config=config, registry=LibraryRegistry(config.index.db_path), agent=default_agent, agent_factory=agent_factory, job_tracker=DocsJobTracker())
    service._agent_instance().query("project query")
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/")

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands")

    assert result.status == "success"
    assert [chunk.content for chunk in result.results] == ["Click command docs."]
    assert default_agent.query_calls == ["project query"]
    # Record-specific lexical retrieval must receive the user's topic unchanged;
    # library scope is already enforced by this per-record agent/index.
    assert library_agent.query_calls == ["commands"]


def test_chunks_without_library_id_are_filtered_out(tmp_path, monkeypatch):
    agent = RecordingAgent([_chunk("Unlabeled chunk.", "https://click.palletsprojects.com/en/8.1.x/commands/", {})])
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/")

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands")

    assert result.status == "empty_library_index"
    assert result.results == []


def test_project_path_in_get_library_docs_does_not_leak_project_docs(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    agent = RecordingAgent(
        [
            _chunk("Click command docs.", "https://click.palletsprojects.com/en/8.1.x/commands/", {"library_id": "python:click@8.1.7:api", "canonical_id": "python:click@8.1.7:api", "ecosystem": "python", "version": "8.1.7"}),
            _chunk("Project README.", str(project / "README.md"), {"library_id": "python:click@8.1.7:api", "project_path": str(project)}),
        ]
    )
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/")

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands", project_path=str(project))

    assert [chunk.content for chunk in result.results] == ["Click command docs."]


def test_post_retrieval_guard_drops_wrong_ecosystem(tmp_path, monkeypatch):
    agent = RecordingAgent([_chunk("Pub Click docs.", "https://click.palletsprojects.com/en/8.1.x/commands/", {"library_id": "python:click@8.1.7:api", "canonical_id": "python:click@8.1.7:api", "ecosystem": "pub", "version": "8.1.7"})])
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/")

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands")

    assert result.status == "empty_library_index"
    assert result.results == []


def test_all_chunks_filtered_returns_controlled_error(tmp_path, monkeypatch):
    agent = RecordingAgent([_chunk("FastAPI docs.", "https://fastapi.tiangolo.com/tutorial/", {"library_id": "python:fastapi@0.110.0:api"})])
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/")

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands")

    assert result.status == "empty_library_index"
    assert result.decision == "stop"
    assert result.diagnostics["reason_code"] == "guard_dropped_all"


def test_local_path_with_matching_library_id_is_filtered_out(tmp_path, monkeypatch):
    agent = RecordingAgent(
        [
            _chunk(
                "unrelated local README",
                "/workspace/fixtures/smart_glasses/README.md",
                {"library_id": "python:click@8.1.7:api"},
            )
        ]
    )
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="click", ecosystem="python", version="8.1.7", docs_url="https://click.palletsprojects.com/en/8.1.x/")

    result = service.get_docs("click", ecosystem="python", version="8.1.7", source_type="api", topic="commands")

    assert result.status == "empty_library_index"
    assert result.results == []
    assert {"code": "wrong_docset_root", "blocking": False, "dropped": 1} in result.diagnostics["warnings"]



def test_failed_registered_library_source_does_not_auto_refresh_on_query(tmp_path, monkeypatch):
    agent = RecordingAgent([])
    service = _service(tmp_path, monkeypatch, agent)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    service.registry.upsert(
        library="flutter-api",
        ecosystem="flutter",
        version="stable",
        docs_url="https://api.flutter.dev",
        source_type="api",
        now=now,
        status="failed",
        last_refreshed_at=now,
        last_error="Dartdoc extraction found no usable documentation content",
    )

    result = service.get_docs("flutter-api", ecosystem="flutter", version="stable", source_type="api", topic="StatefulWidget build")

    assert result.status == "error"
    assert result.reason_code == "registered_source_failed"
    assert result.results == []
    assert agent.add_calls == []
    assert result.diagnostics["reason_code"] == "registered_source_failed"


def test_low_relevance_library_context_is_retained_but_not_supported(tmp_path, monkeypatch):
    agent = RecordingAgent([
        _chunk(
            "Riverpod migration updateShouldNotify changed behavior for generated providers.",
            "https://pub.dev/documentation/flutter_riverpod/latest/migration",
            {"library_id": "pub:flutter_riverpod@latest:api", "canonical_id": "pub:flutter_riverpod@latest:api", "ecosystem": "pub", "version": "latest"},
        )
    ])
    service = _service(tmp_path, monkeypatch, agent)
    _register(service, library="flutter_riverpod", ecosystem="pub", version="latest", docs_url="https://pub.dev/documentation/flutter_riverpod/latest/")

    result = service.get_docs("flutter_riverpod", ecosystem="pub", version="latest", source_type="api", topic="NotifierProvider ref watch AsyncValue")

    assert result.status == "success"
    assert result.context_available is True
    assert result.answer_supported is False
    assert result.answer_available is False
    assert result.support_status == "insufficient_evidence"
    assert result.reason_code == "required_evidence_missing"
    assert result.mandatory_coverage < 1.0
    assert result.missing_requirement_ids
    assert result.results
