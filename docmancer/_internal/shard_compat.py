"""Compatibility bridges for public façades backed by private implementation shards."""
from __future__ import annotations

import functools
import re
import sys
from types import FunctionType
from typing import Any, Iterable


def _safe_identifier(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def _public_namespace_wrapper(
    public_module_name: str,
    public_name: str,
    fn: FunctionType,
    sync: Any,
    *,
    method_kind: str,
) -> FunctionType:
    """Create a wrapper whose ``__globals__`` is the historical public module.

    Besides monkeypatching, some compatibility tests and embedders inspect a
    public function's globals to reach intentionally exposed collaborators. A
    wrapper defined in this helper module would silently move that boundary.
    Generating the tiny wrapper in the façade namespace preserves both seams.
    """

    public_module = sys.modules[public_module_name]
    namespace = vars(public_module)
    token = _safe_identifier(f"{public_name}_{id(fn):x}")
    original_key = f"__docatlas_shard_original_{token}"
    sync_key = f"__docatlas_shard_sync_{token}"
    wrapper_key = f"__docatlas_shard_wrapper_{token}"
    namespace[original_key] = fn
    namespace[sync_key] = sync

    if method_kind == "instance":
        signature = "self, *args, **kwargs"
        call = f"{original_key}(self, *args, **kwargs)"
    elif method_kind == "class":
        signature = "cls, *args, **kwargs"
        call = f"{original_key}(cls, *args, **kwargs)"
    else:
        signature = "*args, **kwargs"
        call = f"{original_key}(*args, **kwargs)"

    exec(
        f"def {wrapper_key}({signature}):\n"
        f"    {sync_key}()\n"
        f"    return {call}\n",
        namespace,
    )
    wrapper = namespace.pop(wrapper_key)
    functools.update_wrapper(wrapper, fn)
    wrapper.__docatlas_shard_bridge__ = True
    return wrapper


def install_class_shard_bridge(
    public_module_name: str,
    public_class: type[Any],
    shard_module_names: Iterable[str],
) -> None:
    """Keep public module monkeypatch seams visible to shard-defined methods."""

    shard_names = tuple(shard_module_names)

    def sync() -> None:
        public_module = sys.modules[public_module_name]
        public_values = vars(public_module)
        for module_name in shard_names:
            shard = sys.modules.get(module_name)
            if shard is None:
                continue
            # Static helpers in legacy implementations sometimes refer to the
            # public class name. Keep that stable after moving the function.
            shard.__dict__[public_class.__name__] = public_class
            for name in tuple(shard.__dict__):
                if name in public_values and not name.startswith("__"):
                    shard.__dict__[name] = public_values[name]

    installed: set[str] = set()
    for base in public_class.__mro__[1:]:
        if base is object:
            continue
        for name, descriptor in vars(base).items():
            if name in installed or (name.startswith("__") and name != "__init__"):
                continue
            installed.add(name)
            if isinstance(descriptor, staticmethod):
                wrapper = _public_namespace_wrapper(
                    public_module_name, name, descriptor.__func__, sync,
                    method_kind="static",
                )
                setattr(public_class, name, staticmethod(wrapper))
            elif isinstance(descriptor, classmethod):
                wrapper = _public_namespace_wrapper(
                    public_module_name, name, descriptor.__func__, sync,
                    method_kind="class",
                )
                setattr(public_class, name, classmethod(wrapper))
            elif isinstance(descriptor, FunctionType):
                wrapper = _public_namespace_wrapper(
                    public_module_name, name, descriptor, sync,
                    method_kind="instance",
                )
                setattr(public_class, name, wrapper)


def install_function_shard_bridge(
    public_module_name: str,
    shard_module_names: Iterable[str],
) -> None:
    """Preserve module-level monkeypatch seams for function-based façades."""

    shard_names = tuple(shard_module_names)
    public_module = sys.modules[public_module_name]

    def sync() -> None:
        public_values = vars(public_module)
        for module_name in shard_names:
            shard = sys.modules.get(module_name)
            if shard is None:
                continue
            for name in tuple(shard.__dict__):
                if name in public_values and not name.startswith("__"):
                    shard.__dict__[name] = public_values[name]

    for name, value in tuple(vars(public_module).items()):
        if name.startswith("_") or not isinstance(value, FunctionType):
            continue
        if getattr(value, "__docatlas_shard_bridge__", False):
            continue
        wrapper = _public_namespace_wrapper(
            public_module_name, name, value, sync, method_kind="static",
        )
        setattr(public_module, name, wrapper)
