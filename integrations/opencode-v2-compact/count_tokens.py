"""JSON text array -> canonical host emergency contract and offline token counts."""
import json
import sys

from docmancer.docs.application.projection_tokenizer import projection_token_count
from docmancer.docs.domain.minimal_context_config import EMERGENCY_TOKENS


if __name__ == "__main__":
    values = json.load(sys.stdin)
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ValueError("Expected an array of text envelopes")
    json.dump({"emergency_tokens": EMERGENCY_TOKENS,
               "counts": [projection_token_count(v.encode("utf-8")) for v in values]}, sys.stdout)
