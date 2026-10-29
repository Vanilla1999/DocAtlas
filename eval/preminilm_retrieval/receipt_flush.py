"""CI-only checkpoint handshake, outside project files and the MCP protocol.

The pinned MCP SDK gives a child only two seconds after closing its stdin. Large
diagnostic receipts must therefore be committed and acknowledged while stdio
is still open. SIGUSR1 wakes an asyncio Event: no diagnostic polling runs in the
worker during measured public calls. No queries, selectors or tool calls change.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import time
import traceback

ARTIFACTS = ("NATIVE.json", "MINILM.json", "SQL.json", "STATE.json")
METHOD = "pre_teardown_sigusr1_checkpoint_v1"
ACK_TIMEOUT_SECONDS = 60.0
ACK_POLL_SECONDS = 0.1


def atomic_save(path: Path, value) -> None:
    """Stream large JSON instead of building additional complete string copies."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError("checkpoint never overwrites an existing artifact: " + path.name)
    pending = path.with_name(path.name + ".pending")
    with pending.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    pending.replace(path)


def file_receipt(path: Path) -> dict:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"sha256": digest, "bytes": path.stat().st_size}


def read_small(path: Path) -> dict:
    if path.stat().st_size > 65536:
        raise ValueError("oversized diagnostic control record")
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("diagnostic control record must be an object")
    return value


def verify_ack(folder: Path, *, request: dict | None = None) -> dict:
    request = request if request is not None else read_small(folder / "FLUSH_REQUEST.json")
    ready = read_small(folder / "FLUSH_READY.json")
    ack = read_small(folder / "FLUSH_ACK.json")
    if (set(request) != {"request_id", "ready_token"}
            or any(not isinstance(request.get(key), str) or len(request[key]) != 32
                   or any(c not in "0123456789abcdef" for c in request[key])
                   for key in ("request_id", "ready_token"))
            or ready.get("method") != METHOD or ready.get("ready_token") != request["ready_token"]
            or type(ready.get("worker_pid")) is not int or ready["worker_pid"] <= 1
            or ack.get("worker_pid") != ready["worker_pid"]
            or ack.get("method") != METHOD or ack.get("request_id") != request["request_id"]
            or ack.get("ready_token") != request["ready_token"]
            or set(ack.get("files", {})) != set(ARTIFACTS)
            or ack.get("worker_poll_count") != 0):
        raise ValueError("diagnostic checkpoint acknowledgment mismatch")
    for name in ARTIFACTS:
        if file_receipt(folder / name) != ack["files"][name]:
            raise ValueError("checkpoint changed after acknowledgment: " + name)
    return ack


async def serve_with_flush(serve, capture, folder: Path) -> None:
    """Run the unchanged server; checkpoint only after the client's final reply."""
    loop = asyncio.get_running_loop()
    requested = asyncio.Event()
    ready_token = secrets.token_hex(16)
    acknowledged = False
    loop.add_signal_handler(signal.SIGUSR1, requested.set)
    atomic_save(folder / "FLUSH_READY.json", {
        "method": METHOD, "worker_pid": os.getpid(), "parent_pid": os.getppid(),
        "ready_token": ready_token, "worker_poll_interval_seconds": 0,
        "worker_poll_count": 0,
    })

    async def checkpoint():
        nonlocal acknowledged
        await requested.wait()
        started = time.monotonic()
        try:
            request = read_small(folder / "FLUSH_REQUEST.json")
            if (request.get("ready_token") != ready_token
                    or not isinstance(request.get("request_id"), str)
                    or len(request["request_id"]) != 32):
                raise ValueError("unexpected diagnostic flush request")
            # Client sends this only after its final call returned; capture
            # disables SQL observation before read-only state checks. There
            # are no awaits between capture and committing the four receipts.
            values = capture()
            if set(values) != set(ARTIFACTS):
                raise ValueError("incomplete diagnostic checkpoint")
            for name in ARTIFACTS:
                atomic_save(folder / name, values[name])
            hashes = {name: file_receipt(folder / name) for name in ARTIFACTS}
            atomic_save(folder / "FLUSH_ACK.json", {
                "method": METHOD, "request_id": request["request_id"], "ready_token": ready_token,
                "worker_pid": os.getpid(), "files": hashes,
                "checkpoint_started_monotonic": started,
                "checkpoint_finished_monotonic": time.monotonic(),
                "worker_poll_interval_seconds": 0, "worker_poll_count": 0,
                "parent_ack_poll_interval_seconds": ACK_POLL_SECONDS,
                "parent_ack_timeout_seconds": ACK_TIMEOUT_SECONDS,
            })
            acknowledged = True
        except Exception as exc:
            atomic_save(folder / "FLUSH_ERROR.json", {"error": str(exc), "traceback": traceback.format_exc()})
            raise

    server_task = asyncio.create_task(serve())
    flush_task = asyncio.create_task(checkpoint())
    try:
        done, _ = await asyncio.wait((server_task, flush_task), return_when=asyncio.FIRST_COMPLETED)
        if flush_task in done:
            await flush_task
            await server_task
        else:
            await server_task
            raise RuntimeError("stdio server exited before diagnostic checkpoint acknowledgment")
    finally:
        loop.remove_signal_handler(signal.SIGUSR1)
        for task in (flush_task, server_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(flush_task, server_task, return_exceptions=True)
        if not acknowledged:
            # Preserve attempted diagnostics on abnormal exit in a separate,
            # explicitly unacknowledged area. Never overwrite the main files
            # or promote a partial write to a successful experiment.
            fallback = folder / "UNACKNOWLEDGED_EXIT"
            try:
                for name, value in capture().items():
                    atomic_save(fallback / name, value)
            except Exception as exc:
                if not (fallback / "ERROR.json").exists():
                    atomic_save(fallback / "ERROR.json", {"error": str(exc)})


async def request_flush(folder: Path) -> dict:
    """Await a bounded, hash-verified ACK before either SDK context exits."""
    ready = read_small(folder / "FLUSH_READY.json")
    if (ready.get("method") != METHOD or ready.get("parent_pid") != os.getpid()
            or type(ready.get("worker_pid")) is not int or ready["worker_pid"] <= 1):
        raise ValueError("diagnostic readiness does not identify this driver's worker")
    request = {"request_id": secrets.token_hex(16), "ready_token": ready["ready_token"]}
    atomic_save(folder / "FLUSH_REQUEST.json", request)
    started = time.monotonic()
    polls = 0
    os.kill(ready["worker_pid"], signal.SIGUSR1)
    while time.monotonic() - started < ACK_TIMEOUT_SECONDS:
        polls += 1
        if (folder / "FLUSH_ERROR.json").exists():
            raise RuntimeError("worker diagnostic checkpoint failed: " + str(read_small(folder / "FLUSH_ERROR.json")))
        if (folder / "FLUSH_ACK.json").exists():
            ack = verify_ack(folder, request=request)
            result = {"method": METHOD, "status": "acknowledged", "seconds": time.monotonic() - started,
                      "parent_ack_polls": polls, "parent_ack_poll_interval_seconds": ACK_POLL_SECONDS,
                      "worker_poll_count_during_public_calls": 0,
                      "artifact_bytes": sum(item["bytes"] for item in ack["files"].values())}
            atomic_save(folder / "FLUSH_CLIENT.json", result)
            return result
        await asyncio.sleep(ACK_POLL_SECONDS)
    raise TimeoutError("diagnostic checkpoint was not acknowledged within 60 seconds")
