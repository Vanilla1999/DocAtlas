"""Split tests from test_unified_docs_context_mcp.py; shared helpers remain in the façade module."""
from tests import _shared_test_unified_docs_context_mcp as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})




