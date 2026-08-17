"""Implementation shard 1 for isolated_delivery."""
from __future__ import annotations

from ._isolated_delivery_shared import *  # noqa: F401,F403


class IsolatedDeliveryError(RuntimeError):
    """A fail-closed host capability or worker-result failure."""


def derive_task33_retrieval_query(task_objective: str) -> str:
    """Derive a frozen project-doc query from the brief without evaluator hints."""

    if not isinstance(task_objective, str) or not task_objective.strip():
        raise IsolatedDeliveryError("invalid_task_objective_for_query_derivation")
    words = [
        token.casefold().strip("-_")
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", task_objective)
    ]
    candidates = [word for word in words if len(word) >= 4 and word not in _TASK33_QUERY_STOP_WORDS]
    counts = {word: candidates.count(word) for word in set(candidates)}
    selected: list[str] = []
    for word in candidates:
        if counts[word] >= 2 and word not in selected:
            selected.append(word)
    # Repeated domain terms anchor the query. Add at most two objective-owned
    # domain details so the query spans offline/sync behavior without turning
    # every narrative word into a completeness requirement.
    if selected:
        for word in _TASK33_DOMAIN_DETAIL_TERMS:
            if word in candidates and word not in selected:
                selected.append(word)
            if len(selected) >= 6:
                break
    else:
        for word in candidates:
            if word not in selected:
                selected.append(word)
            if len(selected) >= 6:
                break
    query = " ".join(selected[:6])
    if not query:
        raise IsolatedDeliveryError("task33_retrieval_query_derivation_empty")
    return query


@dataclass(frozen=True)
class IsolatedWorkerCapabilities:
    fresh_context: bool
    read_only_documentation: bool
    recursive_delegation_disabled: bool
    hard_timeout: bool
    token_accounting: bool
    host_owned_evidence: bool = False
    network_disabled: bool = False
    descendant_containment: bool = False

    @property
    def verified(self) -> bool:
        return all(value is True for value in asdict(self).values())


@dataclass(frozen=True)
class DelegationEnvelope:
    task_objective: str
    suspected_modules: tuple[str, ...]
    changed_files: tuple[str, ...]
    required_evidence_categories: tuple[str, ...]
    project_revision: str
    index_revision: str
    required_evidence_paths: tuple[str, ...] = ()
    packet_schema_version: int = ACTION_PACKET_SCHEMA_VERSION
    token_budget: int = 1_500
    schema_version: int = 1

    def validate(self) -> None:
        if isinstance(self.schema_version, bool) or self.schema_version != 1:
            raise IsolatedDeliveryError("unsupported_delegation_schema")
        if isinstance(self.packet_schema_version, bool) or self.packet_schema_version != ACTION_PACKET_SCHEMA_VERSION:
            raise IsolatedDeliveryError("unsupported_action_packet_schema")
        if not isinstance(self.task_objective, str) or not self.task_objective.strip() or len(self.task_objective) > 1_000:
            raise IsolatedDeliveryError("invalid_task_objective")
        if (
            not isinstance(self.project_revision, str) or not isinstance(self.index_revision, str)
            or not self.project_revision.strip() or not self.index_revision.strip()
            or len(self.project_revision) > 200 or len(self.index_revision) > 200
        ):
            raise IsolatedDeliveryError("missing_revision_identity")
        if (
            isinstance(self.token_budget, bool) or not isinstance(self.token_budget, int)
            or not 128 <= self.token_budget <= HARD_ACTION_PACKET_TOKENS
        ):
            raise IsolatedDeliveryError("invalid_token_budget")
        if not isinstance(self.required_evidence_categories, tuple) or not self.required_evidence_categories:
            raise IsolatedDeliveryError("missing_required_evidence_categories")
        for field_name in (
            "suspected_modules", "changed_files", "required_evidence_categories",
            "required_evidence_paths",
        ):
            values = getattr(self, field_name)
            if (
                not isinstance(values, tuple) or len(values) > 32
                or any(
                    not isinstance(value, str) or not value.strip()
                    or value != value.strip() or len(value) > 500
                    for value in values
                )
                or len(set(values)) != len(values)
            ):
                raise IsolatedDeliveryError(f"invalid_{field_name}")
        encoded = json.dumps(asdict(self), ensure_ascii=False, sort_keys=True).encode("utf-8")
        if len(encoded) > 12_000:
            raise IsolatedDeliveryError("delegation_envelope_too_large")

    def to_json(self) -> dict[str, Any]:
        self.validate()
        return {
            **asdict(self),
            "suspected_modules": list(self.suspected_modules),
            "changed_files": list(self.changed_files),
            "required_evidence_categories": list(self.required_evidence_categories),
            "required_evidence_paths": list(self.required_evidence_paths),
        }

    @property
    def fingerprint(self) -> str:
        return _json_sha256(self.to_json())


@dataclass(frozen=True)
class HostEvidenceSnapshot:
    """Immutable retrieval result owned and counted by the benchmark host."""

    query: str
    objective_sha256: str
    query_derivation: str
    evidence_items: tuple[dict[str, Any], ...]
    trust_contract: dict[str, Any]
    retrieval_issues: tuple[str, ...]
    evidence_categories: tuple[str, ...]
    project_revision: str
    index_revision: str
    response_status: str
    raw_retrieval_tokens: int
    retrieval_wall_time_seconds: float
    retrieval_calls: int = 1
    schema_version: int = 1

    @property
    def fingerprint(self) -> str:
        return _json_sha256(self.to_json(include_content=True))

    def validate(self, envelope: DelegationEnvelope | None = None) -> None:
        if isinstance(self.schema_version, bool) or self.schema_version != 1:
            raise IsolatedDeliveryError("unsupported_host_evidence_schema")
        if not isinstance(self.query, str) or not self.query.strip() or len(self.query) > 1_000:
            raise IsolatedDeliveryError("invalid_host_retrieval_query")
        if not isinstance(self.objective_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.objective_sha256):
            raise IsolatedDeliveryError("invalid_host_objective_fingerprint")
        if self.query_derivation != TASK33_QUERY_DERIVATION:
            raise IsolatedDeliveryError("unsupported_host_query_derivation")
        if (
            isinstance(self.retrieval_calls, bool)
            or not isinstance(self.retrieval_calls, int)
            or self.retrieval_calls != 1
        ):
            raise IsolatedDeliveryError("host_must_retrieve_exactly_once")
        if not isinstance(self.response_status, str) or self.response_status != "success":
            raise IsolatedDeliveryError(f"host_retrieval_not_successful:{self.response_status}")
        if not isinstance(self.evidence_items, tuple) or not self.evidence_items:
            raise IsolatedDeliveryError("host_retrieval_returned_no_evidence")
        if any(not isinstance(item, dict) for item in self.evidence_items):
            raise IsolatedDeliveryError("invalid_host_evidence_item")
        if not isinstance(self.trust_contract, dict):
            raise IsolatedDeliveryError("invalid_host_trust_contract")
        if (
            not isinstance(self.retrieval_issues, tuple)
            or len(self.retrieval_issues) > 64
            or any(not isinstance(issue, str) or not issue.strip() or len(issue) > 1_000 for issue in self.retrieval_issues)
        ):
            raise IsolatedDeliveryError("invalid_host_retrieval_issues")
        if (
            isinstance(self.raw_retrieval_tokens, bool)
            or not isinstance(self.raw_retrieval_tokens, int)
            or self.raw_retrieval_tokens < 0
        ):
            raise IsolatedDeliveryError("invalid_host_raw_retrieval_tokens")
        if (
            isinstance(self.retrieval_wall_time_seconds, bool)
            or not isinstance(self.retrieval_wall_time_seconds, (int, float))
            or not math.isfinite(float(self.retrieval_wall_time_seconds))
            or self.retrieval_wall_time_seconds < 0
        ):
            raise IsolatedDeliveryError("invalid_host_retrieval_wall_time")
        if (
            not isinstance(self.project_revision, str) or not isinstance(self.index_revision, str)
            or not self.project_revision.strip() or not self.index_revision.strip()
        ):
            raise IsolatedDeliveryError("missing_host_revision_identity")
        if (
            not isinstance(self.evidence_categories, tuple) or not self.evidence_categories
            or any(not isinstance(category, str) or not category.strip() for category in self.evidence_categories)
            or len(set(self.evidence_categories)) != len(self.evidence_categories)
        ):
            raise IsolatedDeliveryError("invalid_host_evidence_categories")
        encoded = json.dumps(self.to_json(include_content=True), ensure_ascii=False, sort_keys=True).encode("utf-8")
        if len(encoded) > 2_000_000:
            raise IsolatedDeliveryError("host_evidence_snapshot_too_large")
        if envelope is not None:
            expected_objective_sha256 = hashlib.sha256(envelope.task_objective.encode("utf-8")).hexdigest()
            if self.objective_sha256 != expected_objective_sha256:
                raise IsolatedDeliveryError("host_objective_fingerprint_mismatch")
            if self.query != derive_task33_retrieval_query(envelope.task_objective):
                raise IsolatedDeliveryError("host_query_derivation_mismatch")
            if self.project_revision != envelope.project_revision or self.index_revision != envelope.index_revision:
                raise IsolatedDeliveryError("host_evidence_revision_mismatch")
            missing = sorted(set(envelope.required_evidence_categories) - set(self.evidence_categories))
            if missing:
                raise IsolatedDeliveryError("host_evidence_categories_missing:" + ",".join(missing))

    def manifest(self) -> dict[str, Any]:
        rows = []
        for index, item in enumerate(self.evidence_items):
            rows.append({
                "index": index,
                "path": _source_path(item),
                "section": _source_section(item),
                "content_sha256": hashlib.sha256(str(item.get("content") or "").encode("utf-8")).hexdigest(),
                "item_sha256": _json_sha256(item),
            })
        return {
            "schema_version": 1,
            "query_sha256": hashlib.sha256(self.query.encode("utf-8")).hexdigest(),
            "objective_sha256": self.objective_sha256,
            "query_derivation": self.query_derivation,
            "evidence_fingerprint": self.fingerprint,
            "evidence_categories": list(self.evidence_categories),
            "project_revision": self.project_revision,
            "index_revision": self.index_revision,
            "response_status": self.response_status,
            "retrieval_calls": self.retrieval_calls,
            "raw_retrieval_tokens": self.raw_retrieval_tokens,
            "retrieval_wall_time_seconds": self.retrieval_wall_time_seconds,
            "retrieval_issues": list(self.retrieval_issues),
            "items": rows,
        }

    def to_json(self, *, include_content: bool) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "query": self.query,
            "objective_sha256": self.objective_sha256,
            "query_derivation": self.query_derivation,
            "trust_contract": self.trust_contract,
            "retrieval_issues": list(self.retrieval_issues),
            "evidence_categories": list(self.evidence_categories),
            "project_revision": self.project_revision,
            "index_revision": self.index_revision,
            "response_status": self.response_status,
            "raw_retrieval_tokens": self.raw_retrieval_tokens,
            "retrieval_wall_time_seconds": self.retrieval_wall_time_seconds,
            "retrieval_calls": self.retrieval_calls,
        }
        if include_content:
            payload["evidence_items"] = list(self.evidence_items)
        else:
            payload["evidence_manifest"] = self.manifest()["items"]
        return payload

    def worker_payload(self, envelope: DelegationEnvelope) -> dict[str, Any]:
        self.validate(envelope)
        return {
            "schema_version": 1,
            "envelope": envelope.to_json(),
            "host_evidence": {
                "fingerprint": self.fingerprint,
                "items": list(self.evidence_items),
                "trust_contract": self.trust_contract,
                "retrieval_issues": list(self.retrieval_issues),
                "categories": list(self.evidence_categories),
            },
        }


@dataclass(frozen=True)
class WorkerUsage:
    provider: str
    model: str
    request_id: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int | None = None
    proof: dict[str, Any] | None = None

    def validate(self) -> None:
        for key in ("provider", "model", "request_id"):
            value = getattr(self, key)
            if not isinstance(value, str) or not value.strip() or len(value) > 300:
                raise IsolatedDeliveryError(f"invalid_worker_usage_{key}")
        for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
            value = getattr(self, key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise IsolatedDeliveryError(f"invalid_worker_usage_{key}")
        if not isinstance(self.proof, dict) or self.proof.get("schema_version") != 1:
            raise IsolatedDeliveryError("missing_verified_worker_usage_proof")
        expected = {
            "provider": self.provider,
            "model": self.model,
            "request_id": self.request_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
        }
        if any(self.proof.get(key) != value for key, value in expected.items()):
            raise IsolatedDeliveryError("worker_usage_proof_mismatch")

    @property
    def proof_fingerprint(self) -> str:
        self.validate()
        return _json_sha256(self.proof)

    @classmethod
    def from_json(cls, value: Any) -> "WorkerUsage":
        if not isinstance(value, dict) or set(value) != {
            "provider", "model", "request_id", "input_tokens", "output_tokens", "reasoning_tokens", "proof",
        }:
            raise IsolatedDeliveryError("invalid_worker_usage_contract")
        for key in ("provider", "model", "request_id"):
            if not isinstance(value.get(key), str) or not value[key].strip() or len(value[key]) > 300:
                raise IsolatedDeliveryError(f"invalid_worker_usage_{key}")
        for key in ("input_tokens", "output_tokens", "reasoning_tokens"):
            item = value.get(key)
            if item is not None and (isinstance(item, bool) or not isinstance(item, int) or item < 0):
                raise IsolatedDeliveryError(f"invalid_worker_usage_{key}")
        if value["reasoning_tokens"] is None:
            reasoning = None
        else:
            reasoning = int(value["reasoning_tokens"])
        result = cls(
            provider=value["provider"],
            model=value["model"],
            request_id=value["request_id"],
            input_tokens=value["input_tokens"],
            output_tokens=value["output_tokens"],
            reasoning_tokens=reasoning,
            proof=value["proof"],
        )
        result.validate()
        return result


@dataclass(frozen=True)
class IsolatedWorkerOutput:
    packet: dict[str, Any]
    usage: WorkerUsage
    wall_time_seconds: float


class IsolatedWorker(Protocol):
    @property
    def capabilities(self) -> IsolatedWorkerCapabilities: ...

    @property
    def compressor_identity(self) -> str: ...

    @property
    def command_fingerprint(self) -> str: ...

    @property
    def sandbox_identity(self) -> str: ...

    @property
    def capability_evidence(self) -> dict[str, Any]: ...

    @property
    def usage_verifier_identity(self) -> str: ...

    def run(
        self,
        envelope: DelegationEnvelope,
        evidence: HostEvidenceSnapshot,
        *,
        timeout_seconds: int,
    ) -> IsolatedWorkerOutput:
        """Compress host-owned evidence in one fresh sandboxed process."""


def _communicate_bounded(
    process: subprocess.Popen[bytes],
    payload: bytes,
    *,
    deadline: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
) -> tuple[bytes, bytes]:
    if process.stdin is None or process.stdout is None or process.stderr is None:
        _kill_process_group(process)
        raise IsolatedDeliveryError("isolated_worker_pipe_setup_failed")
    selector = selectors.DefaultSelector()
    streams = {
        process.stdin.fileno(): (process.stdin, "stdin"),
        process.stdout.fileno(): (process.stdout, "stdout"),
        process.stderr.fileno(): (process.stderr, "stderr"),
    }
    for fd, (stream, name) in streams.items():
        os.set_blocking(fd, False)
        selector.register(stream, selectors.EVENT_WRITE if name == "stdin" else selectors.EVENT_READ, name)
    sent = 0
    stdout = bytearray()
    stderr = bytearray()
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _kill_process_group(process)
                raise IsolatedDeliveryError("isolated_worker_timeout")
            events = selector.select(min(remaining, 0.1))
            if not events and process.poll() is not None:
                for stream in (process.stdout, process.stderr):
                    try:
                        chunk = os.read(stream.fileno(), 65_536)
                    except (BlockingIOError, OSError):
                        chunk = b""
                    target = stdout if stream is process.stdout else stderr
                    target.extend(chunk)
                    try:
                        selector.unregister(stream)
                    except (KeyError, ValueError):
                        pass
                if process.stdin in [key.fileobj for key in selector.get_map().values()]:
                    try:
                        selector.unregister(process.stdin)
                    except (KeyError, ValueError):
                        pass
                continue
            for key, _mask in events:
                name = key.data
                stream = key.fileobj
                if name == "stdin":
                    try:
                        written = os.write(stream.fileno(), payload[sent:sent + 65_536])
                    except BrokenPipeError:
                        written = 0
                        sent = len(payload)
                    sent += written
                    if sent >= len(payload):
                        selector.unregister(stream)
                        stream.close()
                else:
                    try:
                        chunk = os.read(stream.fileno(), 65_536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(stream)
                        continue
                    target = stdout if name == "stdout" else stderr
                    target.extend(chunk)
                    limit = max_stdout_bytes if name == "stdout" else max_stderr_bytes
                    if len(target) > limit:
                        _kill_process_group(process)
                        raise IsolatedDeliveryError(f"isolated_worker_{name}_too_large")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _kill_process_group(process)
            raise IsolatedDeliveryError("isolated_worker_timeout")
        process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        _kill_process_group(process)
        raise IsolatedDeliveryError("isolated_worker_timeout") from exc
    finally:
        selector.close()
    return bytes(stdout), bytes(stderr)


def _kill_process_group(process: subprocess.Popen[Any]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _limit_worker_resources(*, timeout_seconds: int, memory_limit_bytes: int, process_limit: int):
    def apply() -> None:
        cpu = max(1, int(math.ceil(timeout_seconds)))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
        resource.setrlimit(resource.RLIMIT_NPROC, (process_limit, process_limit))
        resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))

    return apply


def _is_system_worker_path(path: Path) -> bool:
    allowed = (Path("/usr"), Path("/bin"))
    return any(path == root or root in path.parents for root in allowed)


def _source_path(item: dict[str, Any]) -> str:
    source = item.get("source") if isinstance(item.get("source"), dict) else {}
    return str(item.get("path") or source.get("path") or item.get("url") or source.get("url") or "")


def _source_section(item: dict[str, Any]) -> str:
    section = item.get("section") if isinstance(item.get("section"), dict) else {}
    return str(item.get("heading_path") or section.get("heading_path") or item.get("title") or section.get("title") or "")


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return "unavailable"
    return digest.hexdigest()

__all__=['IsolatedDeliveryError', 'derive_task33_retrieval_query', 'IsolatedWorkerCapabilities', 'DelegationEnvelope', 'HostEvidenceSnapshot', 'WorkerUsage', 'IsolatedWorkerOutput', 'IsolatedWorker', '_communicate_bounded', '_kill_process_group', '_limit_worker_resources', '_is_system_worker_path', '_source_path', '_source_section', '_json_sha256', '_file_sha256']
