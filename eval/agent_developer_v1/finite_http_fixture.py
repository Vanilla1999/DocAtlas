"""Frozen DNS/HTTP input for real finite-source fixture preparation.

Only network input is substituted. URL/security policy, robots handling, parsing,
the public prepare/read handlers and committed indices are production code.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from copy import deepcopy
import hashlib
import ipaddress
import json
from pathlib import Path
import sqlite3
import threading
from urllib.parse import urlsplit
from unittest.mock import patch

from eval.agent_developer_v1.current_retrieval_runtime import bytes_sha256, sha256_json

PUBLIC_FIXTURE_IP = "93.184.216.34"
PREPARATION_TIMEOUT_SECONDS = 30
FROZEN_ROBOTS_TEXT = "User-agent: *\nDisallow:\n"


class FrozenHttpInput:
    def __init__(self, documents: dict[str, str]):
        self.documents = dict(documents)
        self.hosts = {urlsplit(url).hostname for url in documents}
        self.responses = {url: text.encode("utf-8") for url, text in documents.items()}
        self.protocol_controls = {
            f"https://{host}/robots.txt": FROZEN_ROBOTS_TEXT for host in self.hosts
        }
        self.responses.update({url: text.encode("utf-8") for url, text in self.protocol_controls.items()})
        self.events = []
        self.phase = "preparation"

    @contextmanager
    def active(self):
        import httpx
        from docmancer.docs import fetch_policy

        def resolve(host):
            self.events.append({"phase": self.phase, "kind": "dns", "host": host})
            if self.phase != "preparation" or host not in self.hosts:
                raise AssertionError("unselected DNS or any read-time network operation")
            return (ipaddress.ip_address(PUBLIC_FIXTURE_IP),)

        def respond(_transport, request):
            host = request.headers.get("host", "")
            raw_path = request.url.raw_path.decode("ascii")
            url = f"https://{host}{raw_path}"
            self.events.append({"phase": self.phase, "kind": "http", "url": url})
            if (self.phase != "preparation" or request.method != "GET"
                    or request.url.scheme != "https" or request.url.host != PUBLIC_FIXTURE_IP
                    or request.extensions.get("sni_hostname") != host or url not in self.responses):
                raise AssertionError("unselected HTTP or any read-time network operation")
            content = self.responses[url]
            return httpx.Response(200, headers={
                "content-type": "text/plain; charset=utf-8",
                "content-length": str(len(content)),
            }, stream=httpx.ByteStream(content), request=request)

        with (
            patch.object(fetch_policy, "resolve_host", resolve),
            patch.object(httpx.HTTPTransport, "handle_request", respond),
        ):
            yield self

    def observation(self) -> dict:
        return {
            "execution": "frozen_dns_http_input",
            "document_sha256": {url: hashlib.sha256(text.encode("utf-8")).hexdigest()
                                for url, text in sorted(self.documents.items())},
            "infrastructure_sha256": {
                url: hashlib.sha256(text.encode("utf-8")).hexdigest()
                for url, text in sorted(self.protocol_controls.items())
            },
            "events": deepcopy(self.events),
        }


def finite_target(row: dict) -> dict:
    """Host-authored bindings come from the frozen source role, never question prose."""
    official = row["source_class"] == "dependency_docs"
    name = "tenacity" if official else "p15-" + row["id"]
    version = "8.2.3" if official else "latest"
    url = row["source"]
    host, path = urlsplit(url).hostname, urlsplit(url).path or "/"
    return {
        "id": row["id"],
        "identity": {"kind": "package", "ecosystem": "python" if official else "web",
                     "name": name},
        "version": {"policy": "exact" if official else "rolling", "requested": version},
        "source": {
            "type": "reference", "url": url, "format": "direct-text",
            "authority": "official_project" if official else "community",
            "version_binding": "exact" if official else "unversioned",
        },
        "scope": {"coverage": "bounded", "seed_urls": [url, f"https://{host}/robots.txt"],
                  "allowed_domains": [host],
                  "path_prefixes": list(dict.fromkeys([path, "/robots.txt"])), "max_pages": 2},
    }


def prepare_external_sources(service, project: Path, targets: list[dict], workspace: Path) -> dict:
    """Run public manifest preparation and wait for its actual fixture job thread."""
    from docmancer.mcp._docs_server_part01 import call_docs_tool_payload

    if not targets:
        return {"manifest": {"version": 2, "targets": []}, "job": None, "records": []}
    manifest = {"version": 2, "targets": targets}
    manifest_path = workspace / "external-docs.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    threads = []
    original_start = threading.Thread.start

    def observe_start(thread, *args, **kwargs):
        target = getattr(thread, "_target", None)
        if getattr(target, "__name__", "") == "_run_prefetch_docs_manifest_job":
            threads.append(thread)
        return original_start(thread, *args, **kwargs)

    with patch.object(threading.Thread, "start", observe_start):
        started = call_docs_tool_payload("prepare_docs", {
            "action": "prefetch_docs_manifest", "project_path": str(project),
            "manifest_path": str(manifest_path), "continue_on_error": False,
        }, service)
    if (started.get("tool") != "prepare_docs" or started.get("action") != "prefetch_docs_manifest"
            or not isinstance(started.get("job_id"), str) or not started["job_id"]
            or len(threads) != 1):
        raise RuntimeError("public finite fixture preparation did not start exactly one job")
    threads[0].join(timeout=PREPARATION_TIMEOUT_SECONDS)
    if threads[0].is_alive():
        raise RuntimeError("public finite fixture preparation did not terminalize")
    job = call_docs_tool_payload("docs_status", {
        "action": "job", "job_id": started["job_id"],
    }, service)
    if (job.get("tool") != "docs_status" or job.get("action") != "job"
            or job.get("job_id") != started["job_id"] or job.get("status") != "succeeded"):
        detail = {key: job.get(key) for key in ("status", "phase", "reason_code", "message", "errors", "warnings") if key in job}
        observed_job = service.jobs.get(started["job_id"])
        if getattr(observed_job, "job_id", None) == started["job_id"]:
            detail["observed_job"] = {
                key: deepcopy(getattr(observed_job, key, None))
                for key in ("job_id", "status", "target_results", "errors", "warnings")
            }
        raise RuntimeError("public finite fixture preparation failed: " + json.dumps(detail, default=str))
    records = []
    for target in targets:
        identity, version = target["identity"], target["version"]["requested"]
        record = service.registry.get(identity["name"], identity["ecosystem"], version, "reference")
        if record is None:
            raise RuntimeError("public preparation omitted a requested library record")
        path = Path(service.agent_gateway.index_config_for(record).index.db_path)
        stored = read_stored_children(path)
        declared = {target["source"]["url"], *target["scope"]["seed_urls"]}
        if {row["path"] for row in stored} != declared:
            raise RuntimeError("public fixture library index differs from its exact finite members")
        records.append({
            "target_id": target["id"], "library_id": record.library_id,
            "name": record.name, "ecosystem": record.ecosystem, "version": record.version,
            "resolved_version": record.resolved_version, "source_type": record.source_type,
            "docs_url": record.docs_url, "docs_snapshot_exact": record.docs_snapshot_exact,
            "status": record.status, "stored_children": stored,
        })
    return {"manifest": manifest,
            "job": {key: job.get(key) for key in ("tool", "action", "job_id", "status")},
            "records": records}


def read_stored_children(path: Path) -> list[dict]:
    """Observe committed active children through a read-only SQLite connection."""
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(row) for row in db.execute(
            "SELECT c.stable_chunk_id, c.source_path AS path, c.display_text, c.display_content_hash, "
            "c.generation_id, c.parent_logical_id, c.source_identity, p.source_content_hash, "
            "c.line_start, c.line_end, c.char_start, c.char_end, c.byte_start, c.byte_end, "
            "c.library_id, c.resolved_version, c.docs_snapshot_exact, c.project_identity, "
            "c.doc_scope, c.source_class, c.authority "
            "FROM retrieval_children c JOIN index_state s ON s.active_generation_id = c.generation_id "
            "LEFT JOIN retrieval_parents p ON p.generation_id = c.generation_id "
            "AND p.logical_id = c.parent_logical_id "
            "ORDER BY c.source_path, c.stable_chunk_id"
        )]
    return rows


def index_state(service, project: Path, documents: dict[str, str], external: dict) -> dict:
    policy = service.member_storage_policy
    indices = {"project": bytes_sha256(policy.db_path)}
    for row in external["records"]:
        record = service.registry.get(row["library_id"])
        if record is None:
            raise RuntimeError("prepared library record disappeared")
        db_path = Path(service.agent_gateway.index_config_for(record).index.db_path)
        indices[row["library_id"]] = bytes_sha256(db_path)
    return {
        "generation": policy.generation(), "index_sha256": indices,
        "catalog_sha256": bytes_sha256(project / "docatlas.project-docs.yaml"),
        "document_sha256": {path: bytes_sha256(project / path) for path in sorted(documents)},
        "registry_records_sha256": sha256_json([
            service.registry.get(row["library_id"]).__dict__ for row in external["records"]
        ]),
    }
