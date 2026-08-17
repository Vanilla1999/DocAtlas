from __future__ import annotations

from ._project_docs_service_shared import *  # noqa: F401,F403

from ._project_docs_service_part01 import _ProjectDocsServicePart01

from ._project_docs_service_part02 import _ProjectDocsServicePart02

from ._project_docs_service_part03 import _ProjectDocsServicePart03

class ProjectDocsService(_ProjectDocsServicePart01, _ProjectDocsServicePart02, _ProjectDocsServicePart03):

    pass



__all__ = [name for name in globals() if not name.startswith("__") and not name.startswith("_ProjectDocsServicePart")]

# Bind the public class into shard globals for static/class-name references.
from . import _project_docs_service_part01 as _impl_project_docs_service_part01
_impl_project_docs_service_part01.ProjectDocsService = ProjectDocsService
from . import _project_docs_service_part02 as _impl_project_docs_service_part02
_impl_project_docs_service_part02.ProjectDocsService = ProjectDocsService
from . import _project_docs_service_part03 as _impl_project_docs_service_part03
_impl_project_docs_service_part03.ProjectDocsService = ProjectDocsService

# Install the generic shard compatibility bridge.
from docmancer._internal.shard_compat import install_class_shard_bridge as _install_class_shard_bridge
_install_class_shard_bridge(__name__, ProjectDocsService, ['docmancer.docs.application._project_docs_service_shared', 'docmancer.docs.application._project_docs_service_part01', 'docmancer.docs.application._project_docs_service_part02', 'docmancer.docs.application._project_docs_service_part03'])
