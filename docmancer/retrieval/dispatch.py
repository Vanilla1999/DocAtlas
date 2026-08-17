"""Top-level retrieval dispatcher.

Takes a query plus the configured mode (``lexical``, ``dense``, ``sparse``,
``hybrid``) and returns a unified ranked list. For multi-signal modes,
candidate lists are fused with RRF and resolved back to FTS5-flavoured
``RetrievedChunk`` objects so the rest of the agent sees a stable shape."""

from __future__ import annotations

from ._dispatch_shared import *  # noqa: F401,F403

from ._dispatch_part01 import _RetrievalDispatcherPart01

from ._dispatch_part02 import _RetrievalDispatcherPart02

class RetrievalDispatcher(_RetrievalDispatcherPart01, _RetrievalDispatcherPart02):

    """Coordinator for lexical / dense / sparse / hybrid retrieval."""



__all__ = [name for name in globals() if not name.startswith("__") and not name.startswith("_RetrievalDispatcherPart")]

# Bind the public class into shard globals for static/class-name references.
from . import _dispatch_part01 as _impl_dispatch_part01
_impl_dispatch_part01.RetrievalDispatcher = RetrievalDispatcher
from . import _dispatch_part02 as _impl_dispatch_part02
_impl_dispatch_part02.RetrievalDispatcher = RetrievalDispatcher

# Install the generic shard compatibility bridge.
from docmancer._internal.shard_compat import install_class_shard_bridge as _install_class_shard_bridge
_install_class_shard_bridge(__name__, RetrievalDispatcher, ['docmancer.retrieval._dispatch_shared', 'docmancer.retrieval._dispatch_part01', 'docmancer.retrieval._dispatch_part02'])
