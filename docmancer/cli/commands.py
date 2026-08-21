from __future__ import annotations

from ._commands_shared import *  # noqa: F401,F403

from ._commands_part01 import *  # noqa: F401,F403

from ._commands_part02 import *  # noqa: F401,F403

from ._commands_part03 import *  # noqa: F401,F403

from ._commands_part04 import *  # noqa: F401,F403

from ._commands_part05 import *  # noqa: F401,F403

# P0.3 state-identity commands are kept in a focused module so filesystem
# ownership and reviewed-plan behavior do not drift across CLI shards.
from .state_commands import clear_index_cmd, migrate_home_cmd  # noqa: F401,E402

__all__=[n for n in globals() if not n.startswith("__")]

# Preserve the historical monkeypatch surface after splitting command callbacks
# into implementation shards. Tests and embedders patch these names on the
# public ``docmancer.cli.commands`` module; synchronize them immediately before
# Click invokes a callback instead of making shard modules a second public API.
def _sync_public_command_overrides() -> None:
    import sys as _sys
    _public = _sys.modules[__name__]
    _names = (
        "Path",
        "_get_config_class",
        "_load_config",
        "_get_agent_class",
        "_create_agent_or_raise_lock_error",
    )
    for _module_name in (
        "docmancer.cli._commands_shared",
        "docmancer.cli._commands_part01",
        "docmancer.cli._commands_part02",
        "docmancer.cli._commands_part03",
        "docmancer.cli._commands_part04",
        "docmancer.cli._commands_part05",
    ):
        _module = _sys.modules.get(_module_name)
        if _module is None:
            continue
        for _name in _names:
            if hasattr(_public, _name):
                setattr(_module, _name, getattr(_public, _name))


def _install_command_override_sync() -> None:
    import functools as _functools
    import click as _click

    for _value in tuple(globals().values()):
        if not isinstance(_value, _click.Command) or _value.callback is None:
            continue
        _callback = _value.callback
        if getattr(_callback, "__docatlas_override_sync__", False):
            continue

        @_functools.wraps(_callback)
        def _wrapped(*args, __callback=_callback, **kwargs):
            _sync_public_command_overrides()
            return __callback(*args, **kwargs)

        _wrapped.__docatlas_override_sync__ = True
        _value.callback = _wrapped


_install_command_override_sync()
