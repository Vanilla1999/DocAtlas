from __future__ import annotations

import hashlib

import pytest

from eval.evidence_quality_v2.reader_experiment import (
    independent_records,
    make_reader_record,
    pair_by_case_id,
)


MODEL = {
    "model": "qwen2.5:1.5b",
    "model_digest": "sha256:model",
    "runtime_version": "ollama-test",
    "chat_template_digest": "sha256:template",
}


def _row(case_id: str):
    return {"id": case_id, "value": case_id}

















