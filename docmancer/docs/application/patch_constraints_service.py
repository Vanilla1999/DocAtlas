from __future__ import annotations

from ._patch_constraints_service_shared import *  # noqa: F401,F403

from ._patch_constraints_service_part01 import _PatchConstraintsServicePart01

from ._patch_constraints_service_part02 import _PatchConstraintsServicePart02

from ._patch_constraints_service_part03 import _PatchConstraintsServicePart03

class PatchConstraintsService(_PatchConstraintsServicePart01, _PatchConstraintsServicePart02, _PatchConstraintsServicePart03):

    """Compile compact repository patch constraints from visible local project sources."""



__all__ = [name for name in globals() if not name.startswith("__") and not name.startswith("_PatchConstraintsServicePart")]

# Bind the public class into shard globals for static/class-name references.
from . import _patch_constraints_service_part01 as _impl_patch_constraints_service_part01
_impl_patch_constraints_service_part01.PatchConstraintsService = PatchConstraintsService
from . import _patch_constraints_service_part02 as _impl_patch_constraints_service_part02
_impl_patch_constraints_service_part02.PatchConstraintsService = PatchConstraintsService
from . import _patch_constraints_service_part03 as _impl_patch_constraints_service_part03
_impl_patch_constraints_service_part03.PatchConstraintsService = PatchConstraintsService

# Install the generic shard compatibility bridge.
from docmancer._internal.shard_compat import install_class_shard_bridge as _install_class_shard_bridge
_install_class_shard_bridge(__name__, PatchConstraintsService, ['docmancer.docs.application._patch_constraints_service_shared', 'docmancer.docs.application._patch_constraints_service_part01', 'docmancer.docs.application._patch_constraints_service_part02', 'docmancer.docs.application._patch_constraints_service_part03'])
