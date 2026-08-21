from __future__ import annotations

import json
import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from docmancer._version import __version__

PRODUCT_ID = "dev.vanilla1999.docatlas"
PRODUCT_NAME = "DocAtlas"
PRODUCT_HOME_ENV = "DOCATLAS_HOME"
LEGACY_HOME_ENV = "DOCMANCER_HOME"
DEFAULT_HOME_NAME = ".docatlas"
LEGACY_HOME_NAME = ".docmancer"
PRIMARY_CONFIG_NAME = "docatlas.yaml"
LEGACY_CONFIG_NAME = "docmancer.yaml"
STATE_OWNER_FILENAME = "state-owner.json"
STATE_SCHEMA_VERSION = 1


class LegacyHomeWarning(DeprecationWarning):
    """Raised when an explicitly configured legacy DocAtlas home is used."""


class StateOwnershipError(RuntimeError):
    """Raised when DocAtlas cannot prove ownership of a writable state root."""


@dataclass(frozen=True)
class HomeResolution:
    path: Path
    source: str
    compatibility_legacy: bool = False


@dataclass(frozen=True)
class StateInspection:
    path: Path
    classification: str
    reasons: tuple[str, ...] = ()
    owner: dict[str, object] | None = None

    @property
    def is_safe_docatlas(self) -> bool:
        return self.classification in {"empty", "legacy_docatlas", "owned_docatlas"}


_FOREIGN_TOP_LEVEL = frozenset({
    "tree",
    "memory.db",
})
_LEGACY_STRONG_PATHS = (
    Path("mcp") / "manifest.json",
    Path("mcp") / "idempotency.db",
    Path("servers"),
    Path("secrets"),
)


def resolve_home(
    *,
    explicit_path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    home_dir: str | Path | None = None,
) -> HomeResolution:
    """Resolve the DocAtlas machine-state root without touching the filesystem.

    ``DOCATLAS_HOME`` is authoritative. ``DOCMANCER_HOME`` is retained only as
    an explicit one-major compatibility input. The legacy default
    ``~/.docmancer`` is never consulted implicitly.
    """

    if explicit_path is not None:
        return HomeResolution(Path(explicit_path).expanduser().resolve(), "explicit")
    values = os.environ if env is None else env
    primary = str(values.get(PRODUCT_HOME_ENV) or "").strip()
    if primary:
        return HomeResolution(Path(primary).expanduser().resolve(), "docatlas_env")
    legacy = str(values.get(LEGACY_HOME_ENV) or "").strip()
    if legacy:
        return HomeResolution(
            Path(legacy).expanduser().resolve(),
            "legacy_env",
            compatibility_legacy=True,
        )
    base = Path(home_dir).expanduser() if home_dir is not None else Path.home()
    return HomeResolution((base / DEFAULT_HOME_NAME).resolve(), "default")


def docatlas_home() -> Path:
    return resolve_home().path


def legacy_default_home(*, home_dir: str | Path | None = None) -> Path:
    base = Path(home_dir).expanduser() if home_dir is not None else Path.home()
    return (base / LEGACY_HOME_NAME).resolve()


def warn_if_legacy_home(resolution: HomeResolution) -> None:
    if resolution.compatibility_legacy:
        warnings.warn(
            f"{LEGACY_HOME_ENV} is deprecated for DocAtlas; use {PRODUCT_HOME_ENV}. "
            "The explicitly configured path is still honored during the 1.x compatibility window.",
            LegacyHomeWarning,
            stacklevel=2,
        )


def _owner_path(path: Path) -> Path:
    return path / STATE_OWNER_FILENAME


def _read_owner(path: Path) -> tuple[dict[str, object] | None, str | None]:
    marker = _owner_path(path)
    if not marker.is_file():
        return None, None
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"invalid ownership marker: {exc.__class__.__name__}"
    if not isinstance(payload, dict):
        return None, "invalid ownership marker: not an object"
    return payload, None


def inspect_state(path: str | Path) -> StateInspection:
    raw = Path(path).expanduser()
    if raw.is_symlink():
        return StateInspection(raw.absolute(), "ambiguous", ("state root is a symlink",))
    root = raw.resolve()
    if not root.exists():
        return StateInspection(root, "missing")
    if not root.is_dir():
        return StateInspection(root, "ambiguous", ("state root is not a plain directory",))

    owner, owner_error = _read_owner(root)
    if owner_error:
        return StateInspection(root, "ambiguous", (owner_error,))
    if owner is not None:
        if owner.get("product_id") == PRODUCT_ID:
            if owner.get("state_schema_version") != STATE_SCHEMA_VERSION:
                return StateInspection(
                    root,
                    "ambiguous",
                    ("unsupported DocAtlas state schema version",),
                    owner,
                )
            return StateInspection(root, "owned_docatlas", owner=owner)
        return StateInspection(root, "foreign", ("ownership marker belongs to another product",), owner)

    try:
        entries = tuple(root.iterdir())
    except OSError as exc:
        return StateInspection(root, "ambiguous", (f"cannot inspect state root: {exc.__class__.__name__}",))
    if not entries:
        return StateInspection(root, "empty")

    foreign = sorted(name for name in _FOREIGN_TOP_LEVEL if (root / name).exists())
    legacy = sorted(path.as_posix() for path in _LEGACY_STRONG_PATHS if (root / path).exists())
    if foreign and legacy:
        return StateInspection(
            root,
            "ambiguous",
            (f"foreign signatures: {', '.join(foreign)}", f"legacy DocAtlas signatures: {', '.join(legacy)}"),
        )
    if foreign:
        return StateInspection(root, "foreign", (f"foreign signatures: {', '.join(foreign)}",))
    if legacy:
        return StateInspection(root, "legacy_docatlas", (f"legacy DocAtlas signatures: {', '.join(legacy)}",))
    return StateInspection(
        root,
        "ambiguous",
        ("non-empty unowned state has no DocAtlas-specific legacy signature",),
    )


def ownership_payload() -> dict[str, object]:
    return {
        "product_id": PRODUCT_ID,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "created_by_version": __version__,
    }


def ensure_owned_home(
    path: str | Path | None = None,
    *,
    allow_legacy_claim: bool = False,
) -> Path:
    """Create/verify a DocAtlas-owned state root before a write.

    A non-empty directory is never claimed unless it is already DocAtlas-owned
    or the caller explicitly allows a strongly-classified legacy DocAtlas root.
    Foreign and ambiguous roots always fail closed.
    """

    root = Path(path).expanduser().resolve() if path is not None else docatlas_home()
    inspection = inspect_state(root)
    if inspection.classification == "owned_docatlas":
        return root
    if inspection.classification in {"foreign", "ambiguous"}:
        raise StateOwnershipError(
            f"refusing to write unowned state root {root}: {inspection.classification}; "
            + "; ".join(inspection.reasons)
        )
    if inspection.classification == "legacy_docatlas" and not allow_legacy_claim:
        raise StateOwnershipError(
            f"legacy DocAtlas state at {root} requires explicit migration/compatibility handling before writes"
        )
    root.mkdir(parents=True, exist_ok=True)
    marker = _owner_path(root)
    if not marker.exists():
        try:
            with marker.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(ownership_payload(), indent=2, sort_keys=True) + "\n")
        except FileExistsError:
            pass
    final = inspect_state(root)
    if final.classification != "owned_docatlas":
        raise StateOwnershipError(f"failed to establish DocAtlas ownership for {root}")
    return root


__all__ = [
    "DEFAULT_HOME_NAME",
    "HomeResolution",
    "LEGACY_CONFIG_NAME",
    "LEGACY_HOME_ENV",
    "LEGACY_HOME_NAME",
    "LegacyHomeWarning",
    "PRIMARY_CONFIG_NAME",
    "PRODUCT_HOME_ENV",
    "PRODUCT_ID",
    "PRODUCT_NAME",
    "STATE_OWNER_FILENAME",
    "STATE_SCHEMA_VERSION",
    "StateInspection",
    "StateOwnershipError",
    "docatlas_home",
    "ensure_owned_home",
    "inspect_state",
    "legacy_default_home",
    "ownership_payload",
    "resolve_home",
    "warn_if_legacy_home",
]
