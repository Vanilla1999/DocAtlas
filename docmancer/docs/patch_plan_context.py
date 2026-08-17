from __future__ import annotations

from ._patch_plan_context_shared import *  # noqa: F401,F403

from ._patch_plan_context_part01 import *  # noqa: F401,F403

from ._patch_plan_context_part02 import *  # noqa: F401,F403

__all__=[n for n in globals() if not n.startswith("__")]

# Preserve module-level monkeypatch compatibility across implementation shards.
def _install_shard_override_bridge() -> None:
    import functools as _functools
    import sys as _sys
    import types as _types

    _part_names = (
        "docmancer.docs._patch_plan_context_shared",
        "docmancer.docs._patch_plan_context_part01",
        "docmancer.docs._patch_plan_context_part02",
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
