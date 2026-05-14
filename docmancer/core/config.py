from __future__ import annotations

import warnings
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_user_db_path() -> str:
    return str(Path.home() / ".docmancer" / "docmancer.db")


class IndexConfig(BaseSettings):
    provider: str = "sqlite"
    db_path: str = Field(default_factory=default_user_db_path)
    extracted_dir: str = ""
    model_config = SettingsConfigDict(env_prefix="DOCMANCER_INDEX_", extra="ignore")


class QueryConfig(BaseSettings):
    default_budget: int = Field(default=2400, ge=100)
    default_limit: int = Field(default=8, ge=1)
    default_expand: str = "adjacent"
    model_config = SettingsConfigDict(env_prefix="DOCMANCER_QUERY_", extra="ignore")


class WebFetchConfig(BaseSettings):
    workers: int = Field(default=8, ge=1)
    default_page_cap: int = Field(default=500, ge=1)
    browser_fallback: bool = False
    model_config = SettingsConfigDict(env_prefix="DOCMANCER_WEB_FETCH_", extra="ignore")


class DocmancerConfig(BaseModel):
    index: IndexConfig = Field(default_factory=IndexConfig)
    query: QueryConfig = Field(default_factory=QueryConfig)
    web_fetch: WebFetchConfig = Field(default_factory=WebFetchConfig)

    @classmethod
    def from_yaml(cls, path: Path | str) -> DocmancerConfig:
        path = Path(path)
        with open(path) as f:
            data = yaml.safe_load(f) or {}

        if "registry" in data:
            warnings.warn(
                "registry config is obsolete and has been removed; the key is ignored.",
                DeprecationWarning,
                stacklevel=2,
            )
            data.pop("registry", None)

        if "bench" in data:
            warnings.warn(
                "bench config is obsolete and has been removed; the key is ignored.",
                DeprecationWarning,
                stacklevel=2,
            )
            data.pop("bench", None)

        if "eval" in data:
            warnings.warn(
                "eval config is obsolete and has been removed; the key is ignored.",
                DeprecationWarning,
                stacklevel=2,
            )
            data.pop("eval", None)

        data.pop("packs", None)

        if "index" not in data and isinstance(data.get("vector_store"), dict):
            vector_store = data.get("vector_store") or {}
            local_path = vector_store.get("db_path") or vector_store.get("local_path")
            if local_path:
                legacy_path = Path(str(local_path))
                if legacy_path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
                    data["index"] = {"db_path": local_path}
                else:
                    data["index"] = {"db_path": ".docmancer/docmancer.db"}

        config = cls(**data)
        db_path = Path(config.index.db_path)
        if not db_path.is_absolute():
            config.index.db_path = str((path.parent / db_path).resolve())

        extracted_dir = config.index.extracted_dir
        if extracted_dir:
            extracted_path = Path(extracted_dir)
            if not extracted_path.is_absolute():
                config.index.extracted_dir = str((path.parent / extracted_path).resolve())

        return config

    @classmethod
    def from_env(cls) -> DocmancerConfig:
        return cls()
