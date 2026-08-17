from __future__ import annotations

from ._library_docs_service_shared import *  # noqa: F401,F403

from ._library_docs_service_part01 import _LibraryDocsApplicationServicePart01

from ._library_docs_service_part02 import _LibraryDocsApplicationServicePart02

from ._library_docs_service_part03 import _LibraryDocsApplicationServicePart03

from ._library_docs_service_part04 import _LibraryDocsApplicationServicePart04

class LibraryDocsApplicationService(_LibraryDocsApplicationServicePart01, _LibraryDocsApplicationServicePart02, _LibraryDocsApplicationServicePart03, _LibraryDocsApplicationServicePart04):

    pass



__all__ = [name for name in globals() if not name.startswith("__") and not name.startswith("_LibraryDocsApplicationServicePart")]

# Bind the public class into shard globals for static/class-name references.
from . import _library_docs_service_part01 as _impl_library_docs_service_part01
_impl_library_docs_service_part01.LibraryDocsApplicationService = LibraryDocsApplicationService
from . import _library_docs_service_part02 as _impl_library_docs_service_part02
_impl_library_docs_service_part02.LibraryDocsApplicationService = LibraryDocsApplicationService
from . import _library_docs_service_part03 as _impl_library_docs_service_part03
_impl_library_docs_service_part03.LibraryDocsApplicationService = LibraryDocsApplicationService
from . import _library_docs_service_part04 as _impl_library_docs_service_part04
_impl_library_docs_service_part04.LibraryDocsApplicationService = LibraryDocsApplicationService

# Install the generic shard compatibility bridge.
from docmancer._internal.shard_compat import install_class_shard_bridge as _install_class_shard_bridge
_install_class_shard_bridge(__name__, LibraryDocsApplicationService, ['docmancer.docs.application._library_docs_service_shared', 'docmancer.docs.application._library_docs_service_part01', 'docmancer.docs.application._library_docs_service_part02', 'docmancer.docs.application._library_docs_service_part03', 'docmancer.docs.application._library_docs_service_part04'])
