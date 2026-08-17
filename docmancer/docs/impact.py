from __future__ import annotations

from ._impact_shared import *  # noqa: F401,F403

from ._impact_part01 import *  # noqa: F401,F403

from ._impact_part02 import *  # noqa: F401,F403

from ._impact_part03 import *  # noqa: F401,F403

from ._impact_part04 import *  # noqa: F401,F403

__all__=[n for n in globals() if not n.startswith("__")]

# Keep the historical module-level monkeypatch surface stable after moving
# implementation functions into shards. Public overrides are copied into the
# shard globals at call time, so tests and embedders do not need to know the
# internal module layout.
def _install_shard_override_bridge() -> None:
    import functools as _functools
    import sys as _sys
    import types as _types

    _part_names = (
        "docmancer.docs._impact_shared",
        "docmancer.docs._impact_part01",
        "docmancer.docs._impact_part02",
        "docmancer.docs._impact_part03",
        "docmancer.docs._impact_part04",
    )

    def _sync() -> None:
        _public = _sys.modules[__name__]
        _values = {
            name: value for name, value in vars(_public).items()
            if not name.startswith("__")
        }
        for module_name in _part_names:
            module = _sys.modules.get(module_name)
            if module is not None:
                for name, value in _values.items():
                    if name in module.__dict__:
                        module.__dict__[name] = value

    for _name, _value in tuple(globals().items()):
        if not isinstance(_value, _types.FunctionType) or _name.startswith("_install_"):
            continue

        @_functools.wraps(_value)
        def _wrapped(*args, __fn=_value, **kwargs):
            _sync()
            return __fn(*args, **kwargs)

        globals()[_name] = _wrapped


_install_shard_override_bridge()
