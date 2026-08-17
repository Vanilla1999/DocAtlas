from __future__ import annotations

from ._execution_shared import *  # noqa: F401,F403

from ._execution_part01 import *  # noqa: F401,F403

from ._execution_part02 import *  # noqa: F401,F403

from ._execution_part03 import *  # noqa: F401,F403

from ._execution_part04 import *  # noqa: F401,F403

from ._execution_part05 import *  # noqa: F401,F403

__all__=[n for n in globals() if not n.startswith("__")]

from docmancer._internal.shard_compat import install_function_shard_bridge as _install_function_shard_bridge
_install_function_shard_bridge(
    __name__,
    [
        "eval.task_level._execution_shared",
        "eval.task_level._execution_part01",
        "eval.task_level._execution_part02",
        "eval.task_level._execution_part03",
        "eval.task_level._execution_part04",
        "eval.task_level._execution_part05",
    ],
)
