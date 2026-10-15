from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import resource
import re
import selectors
import signal
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from functools import cached_property
from pathlib import Path
from typing import Any, Callable, Protocol

from docmancer.docs.application.action_packet import (
    ACTION_PACKET_SCHEMA_VERSION,
    validate_action_packet,
)

# Frozen envelope validation policy used by _isolated_delivery_part01. This
# evaluator-local historical name is not imported from/passed to the producer.
HARD_ACTION_PACKET_TOKENS = 2_000
from docmancer.docs.application.model_visible_projection import (
    project_patch_context,
    validate_model_visible_projection,
)




_TASK33_QUERY_STOP_WORDS = frozenset({
    "after", "also", "and", "are", "can", "consistently", "continue", "decisions",
    "deferred", "do", "does", "fix", "for", "from", "have", "into", "local", "not",
    "one", "outcomes", "path", "paths", "reach", "related", "result", "shared", "so",
    "the", "through", "use", "users", "while", "with",
})
_TASK33_DOMAIN_DETAIL_TERMS = (
    "offline", "sync", "architecture", "partial", "handoff", "deferred",
)
TASK33_QUERY_DERIVATION = "task33c-domain-coverage-v4-limit12"

__all__=[n for n in globals() if not n.startswith('__')]
