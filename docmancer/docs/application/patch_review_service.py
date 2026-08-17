from __future__ import annotations

from ._patch_review_service_shared import *  # noqa: F401,F403

from ._patch_review_service_part01 import _PatchReviewServicePart01

from ._patch_review_service_part02 import _PatchReviewServicePart02

class PatchReviewService(_PatchReviewServicePart01, _PatchReviewServicePart02):

    """Generate read-only patch review artifacts for a local project."""



__all__ = [name for name in globals() if not name.startswith("__") and not name.startswith("_PatchReviewServicePart")]

# Bind the public class into shard globals for static/class-name references.
from . import _patch_review_service_part01 as _impl_patch_review_service_part01
_impl_patch_review_service_part01.PatchReviewService = PatchReviewService
from . import _patch_review_service_part02 as _impl_patch_review_service_part02
_impl_patch_review_service_part02.PatchReviewService = PatchReviewService

# Install the generic shard compatibility bridge.
from docmancer._internal.shard_compat import install_class_shard_bridge as _install_class_shard_bridge
_install_class_shard_bridge(__name__, PatchReviewService, ['docmancer.docs.application._patch_review_service_shared', 'docmancer.docs.application._patch_review_service_part01', 'docmancer.docs.application._patch_review_service_part02'])
