"""Eval-only host inputs, never an autonomous-model success claim."""
from copy import deepcopy
import pytest

from eval.evidence_quality_v2.host_control import (
    build_oracle, evidence_envelope, permute, verify_spans, assemble_input,
)









