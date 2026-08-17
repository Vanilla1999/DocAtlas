from __future__ import annotations

from ._sqlite_store_shared import *  # noqa: F401,F403

from ._sqlite_store_part01 import _SQLiteStorePart01

from ._sqlite_store_part02 import _SQLiteStorePart02

from ._sqlite_store_part03 import _SQLiteStorePart03

from ._sqlite_store_part04 import _SQLiteStorePart04

from ._sqlite_store_part05 import _SQLiteStorePart05

class SQLiteStore(_SQLiteStorePart01, _SQLiteStorePart02, _SQLiteStorePart03, _SQLiteStorePart04, _SQLiteStorePart05):

    pass



__all__ = [name for name in globals() if not name.startswith("__") and not name.startswith("_SQLiteStorePart")]

# Bind the public class into shard globals for static/class-name references.
from . import _sqlite_store_part01 as _impl_sqlite_store_part01
_impl_sqlite_store_part01.SQLiteStore = SQLiteStore
from . import _sqlite_store_part02 as _impl_sqlite_store_part02
_impl_sqlite_store_part02.SQLiteStore = SQLiteStore
from . import _sqlite_store_part03 as _impl_sqlite_store_part03
_impl_sqlite_store_part03.SQLiteStore = SQLiteStore
from . import _sqlite_store_part04 as _impl_sqlite_store_part04
_impl_sqlite_store_part04.SQLiteStore = SQLiteStore
from . import _sqlite_store_part05 as _impl_sqlite_store_part05
_impl_sqlite_store_part05.SQLiteStore = SQLiteStore

# Install the generic shard compatibility bridge.
from docmancer._internal.shard_compat import install_class_shard_bridge as _install_class_shard_bridge
_install_class_shard_bridge(__name__, SQLiteStore, ['docmancer.core._sqlite_store_shared', 'docmancer.core._sqlite_store_part01', 'docmancer.core._sqlite_store_part02', 'docmancer.core._sqlite_store_part03', 'docmancer.core._sqlite_store_part04', 'docmancer.core._sqlite_store_part05'])
