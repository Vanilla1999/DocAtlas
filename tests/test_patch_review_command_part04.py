"""Split tests from test_patch_review_command.py; shared helpers remain in the façade module."""
from tests import _shared_test_patch_review_command as _shared
globals().update({k: v for k, v in vars(_shared).items() if not k.startswith("__")})












