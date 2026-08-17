from __future__ import annotations

from ._project_context_service_shared import *  # noqa: F401,F403

from ._project_context_service_part01 import _ProjectContextServicePart01

class ProjectContextService(_ProjectContextServicePart01):

    """Application boundary for composing repo-grounded context packs."""



__all__ = [name for name in globals() if not name.startswith("__") and not name.startswith("_ProjectContextServicePart")]

# Bind the public class into shard globals for static/class-name references.
from . import _project_context_service_part01 as _impl_project_context_service_part01
_impl_project_context_service_part01.ProjectContextService = ProjectContextService

# Install the generic shard compatibility bridge.
from docmancer._internal.shard_compat import install_class_shard_bridge as _install_class_shard_bridge
_install_class_shard_bridge(__name__, ProjectContextService, ['docmancer.docs.application._project_context_service_shared', 'docmancer.docs.application._project_context_service_part01'])
