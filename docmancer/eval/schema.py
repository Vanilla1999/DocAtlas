"""Golden dataset schema for retrieval quality evaluation."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


TaxonomyClass = Literal[
    "exact_api_signature",
    "config_key_cli_flag",
    "conceptual_guide",
    "migration_version_specific",
    "error_message",
    "code_example",
    "multi_doc_query",
    "project_aware_dependency",
]


class ExpectedSource(BaseModel):
    """A source/section that should be present in retrieved results.

    ``source`` and ``title`` are substring matches by default so tiny local
    golden sets can stay stable across absolute path changes.
    """

    source: str | None = None
    title: str | None = None
    section_id: int | None = None
    relevance: int = Field(default=1, ge=0)


class GoldenQuery(BaseModel):
    id: str
    query: str
    taxonomy_class: TaxonomyClass | str
    corpus_snapshot: str | None = None
    version_policy: str | None = None
    project_context: dict[str, Any] | None = None
    expected_sources: list[ExpectedSource] = Field(default_factory=list)
    expected_support_spans: list[str] = Field(default_factory=list)
    required_facts: list[str] = Field(default_factory=list)
    forbidden_sources: list[ExpectedSource] = Field(default_factory=list)
    forbidden_versions: list[str] = Field(default_factory=list)


class GoldenDataset(BaseModel):
    schema_version: int = 1
    corpus_snapshot: str | None = None
    items: list[GoldenQuery]


def normalize_expected_source(value: str | dict[str, Any] | ExpectedSource) -> ExpectedSource:
    if isinstance(value, ExpectedSource):
        return value
    if isinstance(value, str):
        return ExpectedSource(source=value)
    return ExpectedSource.model_validate(value)


def load_golden_dataset(path: str) -> GoldenDataset:
    """Load a JSON/YAML golden dataset.

    Accepted shapes:
    - ``{"items": [...]}``
    - ``[...]``
    String entries in ``expected_sources``/``forbidden_sources`` are expanded
      to ``{"source": <string>}``.
    """

    import json
    from pathlib import Path

    import yaml

    raw_text = Path(path).read_text(encoding="utf-8")
    if path.endswith(('.yaml', '.yml')):
        raw = yaml.safe_load(raw_text)
    else:
        raw = json.loads(raw_text)
    if isinstance(raw, list):
        raw = {"items": raw}
    if not isinstance(raw, dict):
        raise ValueError("Golden dataset must be a mapping with items or a list of items.")

    items = []
    for item in raw.get("items", []):
        item = dict(item)
        item["expected_sources"] = [normalize_expected_source(v).model_dump() for v in item.get("expected_sources", [])]
        item["forbidden_sources"] = [normalize_expected_source(v).model_dump() for v in item.get("forbidden_sources", [])]
        items.append(item)
    raw = {**raw, "items": items}
    return GoldenDataset.model_validate(raw)
