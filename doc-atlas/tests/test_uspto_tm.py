"""Parser + normalizer + streaming-ingest tests for the USPTO connector."""
from __future__ import annotations

import textwrap
import zipfile

import pytest

from docmancer.connectors.fetchers.uspto_tm import (
    ParseStats,
    case_file_to_document,
    iter_case_files,
    iter_uspto_documents,
)
from docmancer.core.config import DocmancerConfig
from docmancer.agent import DocmancerAgent


# A minimal but realistic shape: root element wrapping two <case-file> records,
# one live (status code 700) and one dead (status code 900).
_USPTO_XML = textwrap.dedent(
    """\
    <?xml version="1.0" encoding="UTF-8"?>
    <trademark-applications-daily>
      <case-file>
        <serial-number>75000001</serial-number>
        <case-file-header>
          <filing-date>20200115</filing-date>
          <registration-number>4500001</registration-number>
          <registration-date>20210210</registration-date>
          <status-code>700</status-code>
          <status-date>20210210</status-date>
          <mark-identification>STARBUCKS</mark-identification>
          <mark-drawing-code>1</mark-drawing-code>
        </case-file-header>
        <classifications>
          <classification>
            <international-code>030</international-code>
            <us-code-list><us-code>046</us-code></us-code-list>
            <first-use-anywhere-date>20100101</first-use-anywhere-date>
            <first-use-in-commerce-date>20100201</first-use-in-commerce-date>
          </classification>
        </classifications>
        <case-file-statements>
          <case-file-statement>
            <type-code>GS030</type-code>
            <text>Coffee, tea, and related beverages</text>
          </case-file-statement>
        </case-file-statements>
        <case-file-owners>
          <case-file-owner>
            <party-name>Starbucks Corporation</party-name>
            <party-type>30</party-type>
            <address-1>2401 Utah Ave South, Seattle WA</address-1>
            <nationality><country>US</country></nationality>
          </case-file-owner>
        </case-file-owners>
        <pseudo-marks>
          <pseudo-mark><pseudo-mark-identification>STARBUKS</pseudo-mark-identification></pseudo-mark>
        </pseudo-marks>
        <design-searches>
          <design-search><design-search-code>020101</design-search-code></design-search>
        </design-searches>
      </case-file>
      <case-file>
        <serial-number>75000002</serial-number>
        <case-file-header>
          <filing-date>19950315</filing-date>
          <status-code>900</status-code>
          <mark-identification>OLD MARK</mark-identification>
        </case-file-header>
      </case-file>
    </trademark-applications-daily>
    """
).strip()


def _write_xml(tmp_path, name: str = "uspto.xml") -> str:
    p = tmp_path / name
    p.write_text(_USPTO_XML, encoding="utf-8")
    return str(p)


def _write_zip(tmp_path, name: str = "uspto.zip") -> str:
    inner = tmp_path / "tmp_inner.xml"
    inner.write_text(_USPTO_XML, encoding="utf-8")
    archive = tmp_path / name
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(inner, arcname="apc.xml")
    return str(archive)


def test_iter_case_files_emits_live_only_by_default(tmp_path):
    stats = ParseStats()
    cases = list(iter_case_files(_write_xml(tmp_path), stats=stats))
    assert len(cases) == 1
    cf = cases[0]
    assert cf.serial_number == "75000001"
    assert cf.mark_identification == "STARBUCKS"
    assert cf.registration_number == "4500001"
    assert cf.status_code == "700"
    assert cf.filing_date.isoformat() == "2020-01-15"
    assert [g.international_class_code for g in cf.goods_and_services] == ["030"]
    assert cf.goods_and_services[0].description == "Coffee, tea, and related beverages"
    assert cf.owners[0].party_name == "Starbucks Corporation"
    assert cf.pseudo_marks == ["STARBUKS"]
    assert cf.design_search_codes == ["020101"]
    assert stats.parsed == 2
    assert stats.emitted == 1
    assert stats.skipped_dead == 1
    assert stats.failed == 0


def test_iter_case_files_include_dead(tmp_path):
    cases = list(iter_case_files(_write_xml(tmp_path), live_only=False))
    assert {cf.serial_number for cf in cases} == {"75000001", "75000002"}


def test_iter_case_files_supports_zip(tmp_path):
    cases = list(iter_case_files(_write_zip(tmp_path)))
    assert [cf.serial_number for cf in cases] == ["75000001"]


def test_case_file_to_document_single_section(tmp_path):
    cases = list(iter_case_files(_write_xml(tmp_path)))
    doc = case_file_to_document(cases[0])
    assert doc.source == "uspto-tm://75000001"
    assert doc.metadata["chunking_strategy"] == "single"
    assert doc.metadata["format"] == "uspto-tm"
    assert doc.metadata["serial_number"] == "75000001"
    assert doc.metadata["international_classes"] == ["030"]
    assert doc.metadata["owner_names"] == ["Starbucks Corporation"]
    assert doc.metadata["pseudo_marks"] == ["STARBUKS"]
    # Body must contain searchable text we care about for FTS5.
    body = doc.content
    assert "STARBUCKS" in body
    assert "Class 030" in body
    assert "Coffee, tea, and related beverages" in body
    assert "STARBUKS" in body  # pseudo mark for phonetic-ish lookup
    # No `##` headings — the single-section chunker would otherwise split.
    for line in body.splitlines():
        assert not line.startswith("## "), f"unexpected H2 in body: {line!r}"


def test_streaming_ingest_writes_one_section_per_case_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "uspto.db")
    config.index.extracted_dir = str(tmp_path / "extracted")
    agent = DocmancerAgent(config=config)

    stats = ParseStats()
    total = agent.ingest_records(
        iter_uspto_documents(_write_xml(tmp_path), stats=stats),
        recreate=True,
        batch_size=1,
        with_vectors=False,
    )
    # One live case file → one section. Dead one is skipped.
    assert total == 1
    assert stats.parsed == 2
    assert stats.emitted == 1

    sections = agent.store.list_sections_for_embedding()
    assert len(sections) == 1
    sec = sections[0]
    assert sec["title"].startswith("STARBUCKS")
    assert sec["format"] == "uspto-tm"
    # Confirm FTS5 actually hits the mark text.
    hits = agent.query("STARBUCKS coffee", limit=3, budget=1500)
    assert hits and "STARBUCKS" in hits[0].text


def test_streaming_ingest_respects_limit_and_batches(tmp_path, monkeypatch):
    """Batched commits never reach end-of-stream is still correct."""
    monkeypatch.setenv("DOCMANCER_HOME", str(tmp_path / "home"))
    config = DocmancerConfig()
    config.index.db_path = str(tmp_path / "uspto.db")
    agent = DocmancerAgent(config=config)

    seen_progress: list[tuple[int, int]] = []

    def progress(sources: int, sections: int) -> None:
        seen_progress.append((sources, sections))

    total = agent.ingest_records(
        iter_uspto_documents(_write_xml(tmp_path), live_only=False),
        recreate=True,
        batch_size=1,
        with_vectors=False,
        progress_callback=progress,
    )
    assert total == 2
    # progress_callback fires per-batch and once at the end.
    assert seen_progress[-1] == (2, 2)
