"""Bounded real OpenCode sessions; no scorer, provider or tool-result substitution.

Linux only: the private session leader is deliberately not reaped until its
owned group has been stopped. Its held PID cannot be recycled into an unrelated
group. Detached MCP identities require explicit new launch receipts and retained
pidfds; their groups are never signalled. No global process killing.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import select
import signal
import stat
import subprocess
import sys
import threading
import time

TECHNICAL_REASONS = {"scan_incomplete", "context_emergency_stop", "dependency_incomplete"}


def save_new(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _packet(state: dict, tool: str = "") -> dict:
    if tool != "opencode_read_mcp_resource" and not tool.endswith(
            ("_get_docs_context", "_read_docs_source", "_docs_status")):
        return {}  # Native file contents can themselves be arbitrary JSON.
    for key in ("output", "error"):
        value = state.get(key)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                continue
        if isinstance(value, dict):
            return value
    return {}


def event_failure(event: dict, expected_rejections=()) -> dict | None:
    """Read only tool/CLI envelopes, never look for error words in source text."""
    if event.get("type") == "error":
        return {"kind": "client_error"}
    if event.get("type") != "tool_use":
        return None
    part = event.get("part", {})
    state = part.get("state", {})
    packet = _packet(state, str(part.get("tool", "")))
    reason = packet.get("reason_code")
    detail = {"tool": part.get("tool"), "call_id": part.get("id"), "reason_code": reason}
    if reason in TECHNICAL_REASONS:
        return {"kind": "retrieval_failed", **detail}
    failed = (state.get("status") == "error" or packet.get("status") in {"error", "failed"}
              or packet.get("hard_stop") is True)
    if not failed:
        return None
    # The real-client acceptance deliberately exercises named permission guards.
    # Live comparisons supply no exemptions. A technical reason is never exempt.
    if (part.get("id") in expected_rejections and isinstance(state.get("error"), str)
            and state["error"].startswith("documentation_profile_")):
        return None
    return {"kind": "tool_failed", **detail}


def classify_session(events: list[dict], *, returncode: int | None,
                     expected_rejections=(), termination: str | None = None,
                     capture_errors=()) -> dict:
    failures = [failure for event in events
                if (failure := event_failure(event, expected_rejections)) is not None]
    calls = [event.get("part", {}) for event in events if event.get("type") == "tool_use"]
    retrieval = [part for part in calls if part.get("tool") in {"read", "glob", "grep", "opencode_read_mcp_resource"}
                 or str(part.get("tool", "")).endswith(("_get_docs_context", "_read_docs_source"))]
    technical = any(f["kind"] in {"retrieval_failed", "tool_failed"} for f in failures)
    empty = retrieval and all(_packet(part.get("state", {}), str(part.get("tool", ""))).get("reason_code") in
                             {"no_relevant_source_context", "context_portion_exhausted"} for part in retrieval)
    status = "failed" if technical else "not_observed" if not retrieval else "no_evidence" if empty else "succeeded"
    answer = "\n".join(event.get("part", {}).get("text", "") for event in events
                       if event.get("type") == "text").strip()
    session_status = ("timeout" if termination == "timeout" else "interrupted" if termination else
                      "failed" if returncode != 0 or capture_errors or any(f["kind"] == "client_error" for f in failures)
                      else "finished")
    return {
        "session_status": session_status, "retrieval_status": status,
        "answer_status": "produced" if answer else "not_produced", "answer": answer,
        "failures": failures, "capture_errors": list(capture_errors),
        "tool_calls": len(calls), "retrieval_calls": len(retrieval),
        "expected_host_rejections": [part.get("id") for part in calls
            if part.get("id") in expected_rejections and part.get("state", {}).get("status") == "error"],
        "transport_pass": session_status == "finished" and not failures and bool(answer) and status in {"succeeded", "no_evidence"},
        "answer_quality": "not_graded", "termination": termination,
    }


def _process_state(pid: int) -> dict | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    fields = raw[raw.rfind(")") + 2:].split()
    return {"pid": pid, "state": fields[0], "pgid": int(fields[2]), "sid": int(fields[3]),
            "start_ticks": int(fields[19]), "name": raw[raw.find("(") + 1:raw.rfind(")")]}


def _group_members(group: int) -> list[dict]:
    members = []
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            member = _process_state(int(entry.name))
            if member and member["pgid"] == group:
                members.append(member)
    return sorted(members, key=lambda item: item["pid"])


def _capture_owned_registries(paths, registered, observed, errors, *, final=False):
    """Only explicitly configured, new host-written launch receipts grant ownership."""
    for path in paths:
        if any(row["registry"] == str(path) for row in registered) or str(path) in errors:
            continue
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            if final:
                errors[str(path)] = "owned MCP launch registration missing"
            continue
        try:
            with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
                info = os.fstat(stream.fileno())
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                        or info.st_mode & 0o022 or info.st_nlink != 1):
                    raise ValueError("owned launch registration must be a plain, non-writable-by-others owned file")
                value = stream.read(16385)
            if len(value) > 16384:
                raise ValueError("owned launch registration is oversized")
            data = json.loads(value)
            rows = data.get("processes")
            if (not isinstance(rows, list) or not 1 <= len(rows) <= 2 or
                    any(not isinstance(row, dict) for row in rows) or
                    {row.get("role") for row in rows} not in ({"server"}, {"server", "transport"}) or
                    len({row.get("role") for row in rows}) != len(rows)):
                raise ValueError("expected exactly one owned MCP server and optionally its transport")
            for row in rows:
                if any(type(row.get(key)) is not int or row[key] <= 0 for key in ("pid", "pgid", "sid", "start_ticks")):
                    raise ValueError("invalid owned process identity")
                if row["pid"] in {os.getpid(), os.getppid()} or row.get("pid_namespace") != os.readlink("/proc/self/ns/pid"):
                    raise ValueError("owned process PID namespace/parent mismatch")
            for row in rows:
                held = {**row, "registry": str(path), "pidfd": None}
                try:
                    descriptor = os.pidfd_open(row["pid"])
                except ProcessLookupError:
                    descriptor = None
                if descriptor is not None:
                    try:
                        current = _process_state(row["pid"])
                    except BaseException:
                        os.close(descriptor)
                        raise
                    if current and current["start_ticks"] == row["start_ticks"]:
                        held["pidfd"] = descriptor
                        observed[(row["pid"], row["start_ticks"])] = {**current, "role": row["role"],
                                                                     "registry": str(path)}
                    else:
                        os.close(descriptor)  # This registered identity has exited; never signal a reused PID.
                registered.append(held)
        except json.JSONDecodeError:
            if final:
                errors[str(path)] = "incomplete or malformed owned launch registration"
            # A small freshly created receipt may still be in its writer's flush.
        except Exception as exc:
            errors[str(path)] = type(exc).__name__ + ": " + str(exc)


def _registered_live(registered):
    live = []
    for row in registered:
        descriptor = row["pidfd"]
        if descriptor is None:
            continue
        poll = select.poll()
        poll.register(descriptor, select.POLLIN)
        events = poll.poll(0)
        if any(mask & (select.POLLERR | select.POLLNVAL) for _, mask in events):
            raise RuntimeError("owned pidfd became invalid")
        if not events:
            live.append(row)
    return live


def _cleanup(process: subprocess.Popen, observed: dict, registered, registry_errors) -> dict:
    # Do NOT poll/wait/communicate before this function: WNOWAIT pins the leader.
    group = process.pid
    before = _group_members(group)
    if os.getpgid(group) != group or os.getsid(group) != group:
        raise RuntimeError("private session leader identity changed; refusing group cleanup")
    for member in before:
        observed[(member["pid"], member["start_ticks"])] = member
    signals = []
    remaining = before
    for number, grace in ((signal.SIGTERM, 3.0), (signal.SIGKILL, 3.0)):
        registered_live = _registered_live(registered)
        group_live = any(member["state"] not in {"Z", "X"} for member in remaining)
        if not group_live and not registered_live:
            break
        if group_live:
            try:
                os.killpg(group, number)
                signals.append({"signal": number.name, "private_group": group})
            except ProcessLookupError:
                pass
        for row in registered_live:
            try:
                signal.pidfd_send_signal(row["pidfd"], number)
                signals.append({"signal": number.name, "registered_pid": row["pid"], "role": row["role"]})
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + grace
        while True:
            remaining = _group_members(group)
            if (not any(member["state"] not in {"Z", "X"} for member in remaining)
                    and not _registered_live(registered)) or time.monotonic() >= deadline:
                break
            time.sleep(0.025)
    live = [member for member in remaining if member["state"] not in {"Z", "X"}]
    live_registered = _registered_live(registered)
    escaped = []
    for (pid, ticks) in observed:
        member = _process_state(pid)
        if (member and member["start_ticks"] == ticks and member["pgid"] != group
                and member["state"] not in {"Z", "X"}):
            escaped.append(member)
    # Do not signal a re-parented/setsid process's unverified group. Explicitly
    # registered MCP identities were signalled individually through held pidfds.
    reaped = False
    try:
        process.wait(timeout=1)
        reaped = True
    except subprocess.TimeoutExpired:
        pass
    return {"strategy": "held private group plus explicitly registered MCP pidfds; no foreign-group signals",
            "group": group, "observed_processes": list(observed.values()), "before_cleanup": before,
            "signals": signals, "remaining_live": live, "escaped_live_observed": escaped,
            "registered_processes": [{**{key: value for key, value in row.items() if key != "pidfd"},
                                       "exit_verified": row not in live_registered} for row in registered],
            "registration_errors": dict(registry_errors),
            "no_live_owned_processes": not live and not escaped and not live_registered and not registry_errors,
            "leader_reaped": reaped,
            "boundary": "Private group plus explicit MCP launch registrations/observed identities; unseen detached descendants and GPU VRAM are not measured."}


def launch_session(*, opencode: Path, location: Path, question: str, env: dict[str, str],
                   output: Path, model: str, agent: str, timeout: float = 900,
                   title: str = "Documentation", expected_rejections=(), owned_process_files=()) -> dict:
    """One new standalone session. Returns raw streams and a non-quality receipt.

    `output` and configured MCP registration files must not exist. On a technical
    failure, stop the owned group/registered MCP identities and return a failed
    receipt; never retry or create a session through a global OpenCode server.
    """
    if (sys.platform != "linux" or not hasattr(os, "WNOWAIT") or not hasattr(os, "pidfd_open")
            or not hasattr(signal, "pidfd_send_signal") or not Path("/proc/self/stat").is_file()):
        raise RuntimeError("unsupported lifecycle platform: Linux /proc, pidfd and waitid(WNOWAIT) are required")
    probe = os.pidfd_open(os.getpid())
    os.close(probe)  # Qualify the actual kernel interface before starting a client.
    if not opencode.is_absolute() or not opencode.is_file() or not location.is_absolute() or not location.is_dir():
        raise ValueError("absolute existing OpenCode executable and workspace are required")
    if not output.is_absolute() or timeout <= 0 or not question.strip():
        raise ValueError("new absolute output, positive timeout and unchanged nonempty question are required")
    owned_process_files = tuple(Path(path) for path in owned_process_files)
    for path in owned_process_files:
        parent = path.parent.stat()
        if (not path.is_absolute() or os.path.lexists(path) or not stat.S_ISDIR(parent.st_mode)
                or parent.st_uid != os.getuid() or parent.st_mode & 0o022):
            raise ValueError("MCP launch registries must be new absolute files in an owned non-shared directory")
    output.mkdir(parents=True, exist_ok=False)
    command = [str(opencode), "run", "--standalone", "--format", "json", "--agent", agent,
               "--model", model, "--title", title]
    save_new(output / "launch.json", {"command": command, "cwd": str(location), "question": question,
        "timeout_seconds": timeout, "expected_rejections": list(expected_rejections),
        "owned_process_files": [str(path) for path in owned_process_files],
        "environment_values_recorded": False, "automatic_retries": False})
    events, capture_errors, observed, registered, registry_errors = [], [], {}, [], {}
    failure_seen = threading.Event()
    termination = None
    process = None
    started = time.monotonic()
    cleanup = {"no_live_owned_processes": True, "leader_reaped": True, "not_started": True}
    threads = []

    def reader(pipe, target, parse=False):
        try:
            with target.open("x", encoding="utf-8") as stream:
                for line in pipe:
                    stream.write(line)
                    stream.flush()
                    if parse and line.strip():
                        try:
                            event = json.loads(line)
                            if not isinstance(event, dict):
                                raise ValueError("non-object CLI event")
                        except ValueError:
                            capture_errors.append("non_json_cli_stdout")
                            failure_seen.set()
                            continue
                        events.append(event)
                        if event_failure(event, expected_rejections):
                            failure_seen.set()
        except Exception as exc:
            capture_errors.append(type(exc).__name__)
            failure_seen.set()
        finally:
            pipe.close()

    def writer(pipe):
        try:
            pipe.write(question)
        except BrokenPipeError:
            pass  # The actual CLI exit/event determines the failure.
        finally:
            try:
                pipe.close()
            except BrokenPipeError:
                pass

    try:
        process = subprocess.Popen(command, cwd=location, env=env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", start_new_session=True)
        for args in ((process.stdout, output / "raw.jsonl", True), (process.stderr, output / "stderr.log", False)):
            thread = threading.Thread(target=reader, args=args, daemon=True)
            threads.append(thread)
            thread.start()
        input_thread = threading.Thread(target=writer, args=(process.stdin,), daemon=True)
        threads.append(input_thread)
        input_thread.start()
        deadline, next_snapshot = started + timeout, 0.0
        while True:
            now = time.monotonic()
            _capture_owned_registries(owned_process_files, registered, observed, registry_errors)
            if registry_errors:
                termination = "invalid_process_registration"
                break
            if now >= next_snapshot:
                for member in _group_members(process.pid):
                    observed[(member["pid"], member["start_ticks"])] = member
                next_snapshot = now + 0.25
            if failure_seen.is_set():
                termination = "fail_fast"
                break
            if now >= deadline:
                termination = "timeout"
                break
            if os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
                break  # still unreaped: PID/group cannot be recycled before finally.
            failure_seen.wait(0.025)
    except BaseException:
        termination = "launcher_exception"
        raise
    finally:
        if process is not None:
            try:
                _capture_owned_registries(owned_process_files, registered, observed, registry_errors, final=True)
                cleanup = _cleanup(process, observed, registered, registry_errors)
            except Exception as exc:
                # Losing the ability to verify ownership is a failed cleanup,
                # not permission to use a wider kill rule or erase the receipt.
                cleanup = {"group": process.pid, "cleanup_failed": True,
                           "exception_type": type(exc).__name__, "error": str(exc),
                           "no_live_owned_processes": False,
                           "leader_reaped": process.returncode is not None,
                           "observed_processes": list(observed.values()),
                           "boundary": "Cleanup unverified; no fallback signals to other processes/groups."}
                termination = termination or "cleanup_failure"
        for row in registered:
            if row["pidfd"] is not None:
                os.close(row["pidfd"])
        for thread in threads:
            thread.join(timeout=2)
        if any(thread.is_alive() for thread in threads):
            capture_errors.append("stream_did_not_close_after_owned_process_cleanup")
        code = process.returncode if process is not None else None
        receipt = classify_session(events, returncode=code, expected_rejections=expected_rejections,
                                   termination=termination, capture_errors=capture_errors)
        receipt.update(returncode=code, seconds=time.monotonic() - started, cleanup=cleanup,
                       process_started=process is not None)
        receipt["transport_pass"] = (receipt["transport_pass"] and cleanup["no_live_owned_processes"]
                                     and cleanup["leader_reaped"])
        save_new(output / "receipt.json", receipt)
    return {"stdout": (output / "raw.jsonl").read_text(encoding="utf-8"),
            "stderr": (output / "stderr.log").read_text(encoding="utf-8"),
            "returncode": code, "receipt": receipt}
