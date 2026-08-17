from __future__ import annotations

from ._unified_context_service_shared import *  # noqa: F401,F403

from ._unified_context_service_part01 import _UnifiedDocsContextServicePart01

from ._unified_context_service_part02 import _UnifiedDocsContextServicePart02

class UnifiedDocsContextService(_UnifiedDocsContextServicePart01, _UnifiedDocsContextServicePart02):

    """Route high-level docs-context requests to existing facade methods."""



__all__ = [name for name in globals() if not name.startswith("__") and not name.startswith("_UnifiedDocsContextServicePart")]

# Bind the public class into shard globals for static/class-name references.
from . import _unified_context_service_part01 as _impl_unified_context_service_part01
_impl_unified_context_service_part01.UnifiedDocsContextService = UnifiedDocsContextService
from . import _unified_context_service_part02 as _impl_unified_context_service_part02
_impl_unified_context_service_part02.UnifiedDocsContextService = UnifiedDocsContextService

# Install the generic shard compatibility bridge.
from docmancer._internal.shard_compat import install_class_shard_bridge as _install_class_shard_bridge
_install_class_shard_bridge(__name__, UnifiedDocsContextService, ['docmancer.docs.application._unified_context_service_shared', 'docmancer.docs.application._unified_context_service_part01', 'docmancer.docs.application._unified_context_service_part02'])
