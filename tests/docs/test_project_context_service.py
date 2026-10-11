"""Split test module; helpers live in _shared_test_project_context_service.py."""
from tests.docs import _shared_test_project_context_service as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})
