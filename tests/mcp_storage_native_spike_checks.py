"""Standalone finite native research runner; not a pytest module or CI gate."""
from __future__ import annotations

import hashlib
import errno
import argparse
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import select
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
SPIKE = ROOT / "experiments/mcp_storage_native"
WORKER = SPIKE / "worker.py"
SPEC = importlib.util.spec_from_file_location("storage_spike_worker", WORKER)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


MAX_SCENARIOS = 27
MAX_WORKERS_PER_SCENARIO = 4
MAX_CHECKPOINT_BYTES = 65536
ACTIVE_PROCESSES = []


def admit_runtime():
    if not __debug__:
        raise RuntimeError("research assertions require Python without -O")
    if sys.platform != "linux" or not hasattr(sqlite3.Connection, "load_extension"):
        raise RuntimeError("positive research requires the explicitly reviewed Linux runtime; no skip")
    with sqlite3.connect(":memory:") as probe:
        identity = probe.execute("SELECT sqlite_version(), sqlite_source_id()").fetchone()
        options = [row[0] for row in probe.execute("PRAGMA compile_options")]
    if identity != ("3.50.4", MODULE.EXPECTED_SOURCE_ID) or options != MODULE.EXPECTED_COMPILE_OPTIONS:
        raise RuntimeError("standalone research requires the exact trusted SQLite runtime; no build or skip")
    for name, expected in MODULE.HEADER_HASHES.items():
        assert hashlib.sha256((SPIKE / "include" / name).read_bytes()).hexdigest() == expected


def build_extension(artifact_dir):
    compiler = shutil.which("cc")
    assert compiler, "existing compiler required; no auto-install"
    output = artifact_dir / "spike.so"
    built = subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-Wno-misleading-indentation", "-fPIC", "-shared",
                            str(SPIKE / "sqlite_fd_vfs.c"), "-o", str(output)],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode == 0, built.stderr
    return output


def create_storage(tmp_path):
    root = tmp_path / "fixture"
    root.mkdir()
    database = root / "index.db"
    with sqlite3.connect(database) as conn:
        conn.executescript("CREATE TABLE index_state(id INTEGER PRIMARY KEY,generation TEXT);"
                           "INSERT INTO index_state VALUES(1,'gen-zero');"
                           "CREATE TABLE members(path TEXT PRIMARY KEY,owner TEXT,content TEXT);")
    journal = root / "index.db-journal"
    journal.touch()
    journal.chmod(database.stat().st_mode & 0o777)
    return root, database, journal


def request(**changes):
    return {"operation": "upsert", "expected_generation": "gen-zero",
            "new_generation": "gen-one", "content": "fixture bytes " * 400, **changes}


class Process:
    def __init__(self, extension, storage, req=None, **faults):
        assert len(ACTIVE_PROCESSES) < MAX_WORKERS_PER_SCENARIO, "finite worker budget exceeded"
        ACTIVE_PROCESSES.append(self)
        self.fds = []
        self.trace_file = None
        self.process = None
        self.closed = False
        root, database, journal = storage
        for path, flags in ((database, os.O_RDWR), (journal, os.O_RDWR),
                            (root, os.O_RDONLY | os.O_DIRECTORY)):
            self.fds.append(os.open(path, flags | os.O_NOFOLLOW))
        self.trace_path = root.parent / f"worker-{len(list(root.parent.glob('worker-*.trace')))}.trace"
        self.trace_file = self.trace_path.open("w")
        self.rows = []
        self.pending = ""
        env = {key: value for key, value in os.environ.items() if not key.startswith("SPIKE_")}
        env.update({key: str(value) for key, value in faults.items()})
        self.process = subprocess.Popen([sys.executable, str(WORKER), "--extension", str(extension),
                                         "--database-fd", str(self.fds[0]),
                                         "--journal-fd", str(self.fds[1]),
                                         "--directory-fd", str(self.fds[2])],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.trace_file, text=True, bufsize=1,
                                        pass_fds=self.fds, env=env)
        self.process.stdin.write(json.dumps(req or request()) + "\n")
        self.process.stdin.flush()

    def wait(self, checkpoint):
        deadline = time.monotonic() + 5
        for _ in range(30):
            while "\n" not in self.pending:
                remaining = deadline - time.monotonic()
                assert remaining > 0, f"checkpoint deadline; {self.trace_path}"
                ready, _, _ = select.select([self.process.stdout], [], [], remaining)
                assert ready, f"checkpoint timeout; {self.trace_path}"
                chunk = os.read(self.process.stdout.fileno(), 8192)
                assert chunk, f"worker exited before {checkpoint}: {self.rows}"
                self.pending += chunk.decode()
                assert len(self.pending) <= MAX_CHECKPOINT_BYTES, "checkpoint output budget exceeded"
            line, self.pending = self.pending.split("\n", 1)
            assert line, f"worker exited before {checkpoint}: {self.rows}"
            row = json.loads(line)
            self.rows.append(row)
            if row.get("checkpoint") == checkpoint:
                return
            assert "result" not in row, row
        raise AssertionError("too many startup rows")

    def resume(self):
        self.process.stdin.write("continue\n")
        self.process.stdin.flush()

    def finish(self):
        try:
            text, _ = self.process.communicate(timeout=10)
            self.rows += [json.loads(line) for line in (self.pending + text).splitlines()]
        finally:
            self.close()
        self.trace = [json.loads(line) for line in self.trace_path.read_text().splitlines() if line.startswith("{")]
        self.trace_path.with_suffix(".stdout.jsonl").write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in self.rows) + "\n")
        results = [row["result"] for row in self.rows if "result" in row]
        return results[-1] if results else None

    def close(self):
        if self.closed:
            return
        if self.process is not None:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=5)
            for stream in (self.process.stdin, self.process.stdout):
                if stream is not None:
                    stream.close()
        if self.trace_file is not None:
            self.trace_file.close()
        for fd in self.fds:
            os.close(fd)
        self.closed = True


@contextmanager
def scenario_resources():
    assert not ACTIVE_PROCESSES
    try:
        yield
    finally:
        try:
            for proc in ACTIVE_PROCESSES:
                proc.close()
        finally:
            ACTIVE_PROCESSES.clear()


def ordinary(database):
    # Always an independent process: no raw-close/POSIX-lock interference.
    code = ("import sqlite3,json,sys; c=sqlite3.connect(sys.argv[1],timeout=.15); "
            "print(json.dumps([c.execute('SELECT generation FROM index_state').fetchone()[0], "
            "c.execute('SELECT path,owner,content FROM members ORDER BY path').fetchall()])); c.close()")
    result = subprocess.run([sys.executable, "-c", code, str(database)], capture_output=True,
                            text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def trace_events(proc):
    return [row["event"] for row in proc.trace]


def scenario_exact_profile_and_header_provenance(extension, storage):
    tmp_path = storage[0].parent
    result = subprocess.run([sys.executable, str(WORKER), "--extension", str(extension)],
                            input='{"operation":"profile"}\n', capture_output=True,
                            text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert rows[0]["profile"] == MODULE.EXPECTED_PROFILE
    assert rows[0]["sqlite_version"] == "3.50.4"
    assert rows[0]["compile_options"] == MODULE.EXPECTED_COMPILE_OPTIONS
    assert rows[0]["sqlite_source_id"] == "2025-07-30 19:33:53 4d8adfb30e03f9cf27f800a2c1ba3c48fb4ca1b08b0f5ed59a4d5ecbf45e20a3"
    (tmp_path / "profile.json").write_text(json.dumps(rows, indent=2))


def scenario_experimental_commit_has_actual_exclusive_lock_and_default_read(extension, storage):
    proc = Process(extension, storage)
    result = proc.finish()
    assert result["status"] == "experimental_commit", (result, proc.trace)
    assert result["production_ready"] is False
    events = trace_events(proc)
    assert "vfs_lock_level" in events and "vfs_sync" in events and "vfs_close" in events
    writes = [row for row in proc.trace if row["event"] in {"db_write_attempt", "journal_write_attempt"}]
    assert writes and all(row["lock"] == 4 for row in writes)
    results = [row for row in proc.trace if row["event"] == "write_syscall_result"]
    assert len(results) == len(writes)
    assert all(row["syscall_performed"] and row["errno"] == 0 and
               row["result_bytes"] == row["requested_bytes"] for row in results)
    assert not any("shm" in event for event in events)
    installed = [row["name"] for row in proc.trace if row["event"] == "hook_installed"]
    assert set(installed) == set(MODULE.EXPECTED_PROFILE.split(","))
    assert len(installed) == len(MODULE.EXPECTED_PROFILE.split(","))
    assert any(row["event"] == "posix_lock" and row["start"] == 1073741826 for row in proc.trace)
    assert "unlink_denied" not in events and "vfs_delete_denied" not in events
    generation, members = ordinary(storage[1])
    assert generation == "gen-one" and members == [["README.md", "fixture-owner", request()["content"]]]


def scenario_stale_generation_no_member_attempt_or_clean_fixture_byte_changes(extension, storage):
    before = [path.read_bytes() for path in storage[1:]]
    proc = Process(extension, storage, request(expected_generation="stale"))
    result = proc.finish()
    assert result["error"] == "stale generation"
    assert result["commit_outcome"] == "no_member_write_attempt"
    assert not {"db_write_attempt", "journal_write_attempt"} & set(trace_events(proc))
    assert before == [path.read_bytes() for path in storage[1:]]


def scenario_two_workers_generation_cas(extension, storage):
    first = Process(extension, storage, request(pause="locked"))
    first.wait("locked")
    second = Process(extension, storage)
    loser = second.finish()
    assert "locked" in loser["error"]
    assert not {"db_write_attempt", "journal_write_attempt"} & set(trace_events(second))
    first.resume()
    assert first.finish()["status"] == "experimental_commit"
    stale = Process(extension, storage)
    assert stale.finish()["error"] == "stale generation"


def scenario_independent_default_writer_contention(extension, storage):
    code = ("import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute('BEGIN EXCLUSIVE'); "
            "print('locked',flush=True); sys.stdin.readline(); c.rollback(); c.close()")
    peer = subprocess.Popen([sys.executable, "-c", code, str(storage[1])], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        ready, _, _ = select.select([peer.stdout], [], [], 5)
        assert ready, "independent peer checkpoint timeout"
        assert peer.stdout.readline().strip() == "locked"
        proc = Process(extension, storage)
        result = proc.finish()
        assert "locked" in result["error"]
        assert not {"db_write_attempt", "journal_write_attempt"} & set(trace_events(proc))
    finally:
        try:
            peer.communicate("continue\n", timeout=5)
        finally:
            if peer.poll() is None:
                peer.kill()
                peer.wait(timeout=5)
    assert ordinary(storage[1]) == ["gen-zero", []]


def scenario_replacements_before_locked_recheck_deny_without_foreign_writes(extension, storage, target):
    root, database, journal = storage
    proc = Process(extension, storage, request(pause="bound"))
    proc.wait("bound")
    foreign = root.parent / "foreign"
    foreign.mkdir()
    if target == "directory":
        root.rename(root.parent / "pinned-directory")
        root.mkdir()
        (root / "index.db").write_bytes(b"foreign database")
        (root / "index.db-journal").write_bytes(b"foreign journal")
        before = [(root / name).read_bytes() for name in ("index.db", "index.db-journal")]
    else:
        victim = database if target == "database" else journal
        victim.rename(root / "pinned-old")
        victim.write_bytes(b"foreign inode fixture" * 50)
        before = victim.read_bytes()
    proc.resume()
    result = proc.finish()
    # A directory rename does not change the descriptor namespace: this is
    # precisely the unresolved object-bound versus pathname-grant distinction.
    if target == "directory":
        assert result["status"] == "experimental_commit"
        assert before == [(root / name).read_bytes() for name in ("index.db", "index.db-journal")]
    else:
        assert result["error"] == "fixture namespace replaced"
        assert victim.read_bytes() == before
        assert not {"db_write_attempt", "journal_write_attempt"} & set(trace_events(proc))


def scenario_after_final_check_swaps_do_not_redirect_descriptors(extension, storage, target):
    proc = Process(extension, storage, SPIKE_PAUSE_DB_WRITE=1)
    proc.wait("native_before_db_write")
    victim = storage[1] if target == "database" else storage[2]
    victim.rename(storage[0] / "pinned-old")
    victim.write_bytes(b"foreign object after check" * 500)
    before = victim.read_bytes()
    proc.resume()
    result = proc.finish()
    assert result["status"] == "experimental_commit", result
    assert victim.read_bytes() == before
    # Not an acceptance assertion: the path no longer denotes the committed DB.


def scenario_preexisting_hardlinks_denied(extension, storage, target):
    os.link(storage[target], storage[0] / "external-alias")
    before = storage[target].read_bytes()
    proc = Process(extension, storage)
    result = proc.finish()
    assert result["error"] == "invalid inherited objects"
    assert storage[target].read_bytes() == before
    assert not {"db_write_attempt", "journal_write_attempt"} & set(trace_events(proc))


def scenario_post_pin_alias_detector_not_an_atomic_guarantee(extension, storage):
    proc = Process(extension, storage, SPIKE_PAUSE_DB_WRITE=1)
    proc.wait("native_before_db_write")
    before = storage[1].read_bytes()
    os.link(storage[1], storage[0] / "late-alias")
    proc.resume()
    result = proc.finish()
    assert result["status"] == "error"
    assert result["commit_outcome"] == "unknown"
    assert "link_count_write_denied" in trace_events(proc)
    denied_results = [row for row in proc.trace if row["event"] == "write_syscall_result" and row["kind"] == 1]
    assert denied_results and all(not row["syscall_performed"] and row["result_bytes"] == -1 and
                                  row["errno"] == errno.EPERM for row in denied_results)
    assert storage[1].read_bytes() == before


def scenario_wal_denied_before_any_native_target_write(extension, storage):
    with sqlite3.connect(storage[1]) as conn:
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    storage[2].touch()
    before = storage[1].read_bytes()
    proc = Process(extension, storage)
    result = proc.finish()
    assert result["error"] == "WAL or non-rollback database unsupported"
    assert not {"db_write_attempt", "journal_write_attempt"} & set(trace_events(proc))
    assert storage[1].read_bytes() == before


def scenario_sync_errors_do_not_claim_zero_mutation(extension, storage, number):
    proc = Process(extension, storage, SPIKE_FAIL_SYNC=number)
    result = proc.finish()
    assert result["status"] == "error", (result, proc.trace)
    assert result["commit_outcome"] == "unknown"
    assert "injected_sync_failure" in trace_events(proc)


def scenario_crash_hot_journal_recovery_is_traced_not_zero_write(extension, storage):
    crash = Process(extension, storage, SPIKE_CRASH_DB_WRITE=1)
    assert crash.finish() is None
    assert crash.process.returncode == 86
    assert storage[2].read_bytes()[:8] == bytes.fromhex("d9d505f920a163d7")
    recovery = Process(extension, storage, request(operation="recover"))
    result = recovery.finish()
    assert result["status"] == "recovered", (result, recovery.trace)
    assert {"db_write_attempt", "journal_write_attempt"} & set(trace_events(recovery))
    assert ordinary(storage[1]) == ["gen-zero", []]


def scenario_close_completes_with_no_unlink_or_shm(extension, storage):
    proc = Process(extension, storage)
    assert proc.finish()["status"] == "experimental_commit"
    phases = [row.get("phase") for row in proc.rows]
    assert phases.index("commit_returned") < phases.index("close_start") < phases.index("close_returned")
    assert "unix_close" in trace_events(proc)
    assert not any("denied" in event or "shm" in event for event in trace_events(proc))


def scenario_unknown_fixture_operation_denied_before_binding(extension, storage):
    proc = Process(extension, storage, request(operation="arbitrary_sql"))
    assert proc.finish() is None
    assert proc.process.returncode != 0
    assert not any("inherited_binding_complete" == row.get("event") for row in proc.trace)


def scenario_unknown_native_routes_and_unexpected_shm_are_denied(extension, storage):
    before = [path.read_bytes() for path in storage[1:]]
    proc = Process(extension, storage, request(operation="probe_denials"))
    result = proc.finish()
    assert result["status"] == "error" and result["probe_denials"] == 7
    assert {"unknown_or_destructive_open_denied", "unknown_vfs_access_denied",
            "vfs_delete_denied", "unexpected_shm_map_denied", "unexpected_shm_lock_denied",
            "mmap_denied", "unknown_directory_denied"} <= set(trace_events(proc))
    assert before == [path.read_bytes() for path in storage[1:]]


def scenario_actual_close_eio_independently_latched_without_direct_poison(extension, storage, object_kind):
    proc = Process(extension, storage, SPIKE_CLOSE_EIO_KIND=object_kind)
    result = proc.finish()
    assert result["status"] == "error" and result["commit_outcome"] == "unknown"
    assert result["close_errors"] == 1 and result["close_errno"] == errno.EIO
    failures = [row for row in proc.trace if row["event"] == "close_syscall_result" and row["result"] == -1]
    assert len(failures) == 1 and failures[0]["kind"] == object_kind and failures[0]["errno"] == errno.EIO
    # The fault primitive did not directly poison denial state. SQLite's xClose
    # result may still be OK; the worker must consume the independent latch.
    assert any(row["event"] == "vfs_close_result" and row["value"] == 0 for row in proc.trace)
    assert "injected_close_failure" not in trace_events(proc)
    if object_kind == 1:
        assert result["native_denials"] == 0
        assert any(row.get("phase") == "commit_returned" for row in proc.rows)
        assert ordinary(storage[1])[0] == "gen-one"


def scenario_hostile_hot_journal_removal_exposes_unresolved_crash_obligation(extension, storage):
    before = hashlib.sha256(storage[1].read_bytes()).hexdigest()
    crash = Process(extension, storage, SPIKE_CRASH_DB_WRITE=1)
    assert crash.finish() is None and crash.process.returncode == 86
    assert storage[2].read_bytes()[:8] == bytes.fromhex("d9d505f920a163d7")
    after = hashlib.sha256(storage[1].read_bytes()).hexdigest()
    assert after != before
    # Adversary action on this exact disposable fixture, not cleanup or repair.
    storage[2].unlink()
    observation = {"database_changed_before_commit_return": True,
                   "recovery_journal_survives": storage[2].exists(),
                   "guarantee": "UNRESOLVED; do not infer crash recovery without journal"}
    (storage[0].parent / "hostile-removal-observation.json").write_text(json.dumps(observation, indent=2))
    assert observation["recovery_journal_survives"] is False


def scenario_member_owner_conflict_no_clean_fixture_member_writes(extension, storage):
    with sqlite3.connect(storage[1]) as conn:
        conn.execute("INSERT INTO members VALUES('README.md','unselected-owner','unchanged')")
    storage[2].touch()
    storage[2].chmod(storage[1].stat().st_mode & 0o777)
    before = storage[1].read_bytes()
    proc = Process(extension, storage)
    result = proc.finish()
    assert result["error"] == "member ownership conflict"
    assert result["commit_outcome"] == "no_member_write_attempt"
    assert not {"db_write_attempt", "journal_write_attempt"} & set(trace_events(proc))
    assert storage[1].read_bytes() == before


def scenario_ignored_permission_adjustment_poison_stops_member_writes(extension, storage):
    storage[2].chmod(0o600)
    before = [path.read_bytes() for path in storage[1:]]
    proc = Process(extension, storage)
    result = proc.finish()
    assert result["status"] == "error" and result["native_denials"] > 0
    assert result["commit_outcome"] == "no_member_write_attempt"
    assert "chmod_denied" in trace_events(proc)
    assert not {"db_write_attempt", "journal_write_attempt"} & set(trace_events(proc))
    assert before == [path.read_bytes() for path in storage[1:]]


SCENARIOS = (
    (scenario_exact_profile_and_header_provenance, ()),
    (scenario_experimental_commit_has_actual_exclusive_lock_and_default_read, ()),
    (scenario_stale_generation_no_member_attempt_or_clean_fixture_byte_changes, ()),
    (scenario_two_workers_generation_cas, ()),
    (scenario_independent_default_writer_contention, ()),
    *((scenario_replacements_before_locked_recheck_deny_without_foreign_writes, (target,))
      for target in ("database", "journal", "directory")),
    *((scenario_after_final_check_swaps_do_not_redirect_descriptors, (target,))
      for target in ("database", "journal")),
    *((scenario_preexisting_hardlinks_denied, (target,)) for target in (1, 2)),
    (scenario_post_pin_alias_detector_not_an_atomic_guarantee, ()),
    (scenario_wal_denied_before_any_native_target_write, ()),
    *((scenario_sync_errors_do_not_claim_zero_mutation, (number,)) for number in (1, 2, 3)),
    (scenario_crash_hot_journal_recovery_is_traced_not_zero_write, ()),
    (scenario_close_completes_with_no_unlink_or_shm, ()),
    (scenario_unknown_fixture_operation_denied_before_binding, ()),
    (scenario_unknown_native_routes_and_unexpected_shm_are_denied, ()),
    *((scenario_actual_close_eio_independently_latched_without_direct_poison, (kind,))
      for kind in (1, 2, 3)),
    (scenario_hostile_hot_journal_removal_exposes_unresolved_crash_obligation, ()),
    (scenario_member_owner_conflict_no_clean_fixture_member_writes, ()),
    (scenario_ignored_permission_adjustment_poison_stops_member_writes, ()),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True,
                        help="new absolute disposable directory below /tmp/opencode; retained for audit")
    args = parser.parse_args()
    summary = {"status": "error", "expected_scenarios": MAX_SCENARIOS,
               "passed": 0, "failed": 0, "executed": 0, "scenarios": [], "artifact_dir": None,
               "normal_pytest_gate": False, "production_ready": False, "R1": "OPEN"}
    artifact_dir = None
    try:
        # Before compiler lookup, mkdir, SQLite fixture schema or native artifact.
        admit_runtime()
        assert len(SCENARIOS) == MAX_SCENARIOS
        requested = args.artifact_dir
        if (not requested.is_absolute() or requested != requested.resolve() or
                not requested.is_relative_to(Path("/tmp/opencode")) or
                requested == Path("/tmp/opencode") or not requested.parent.is_dir()):
            raise ValueError("artifact directory must be a new canonical absolute /tmp/opencode child")
        requested.mkdir()  # Never overwrite or remove an existing directory.
        artifact_dir = requested
        summary["artifact_dir"] = str(artifact_dir)
        extension = build_extension(artifact_dir)
        for index, (scenario, parameters) in enumerate(SCENARIOS, 1):
            name = scenario.__name__.removeprefix("scenario_")
            name += "".join("_" + str(value) for value in parameters)
            record = {"scenario": name, "status": "error"}
            summary["scenarios"].append(record)
            folder = artifact_dir / f"{index:02d}_{name}"
            try:
                folder.mkdir()
                with scenario_resources():
                    scenario(extension, create_storage(folder), *parameters)
            except Exception:
                summary["failed"] += 1
                record["traceback"] = traceback.format_exc()
                if folder.is_dir():
                    (folder / "failure.txt").write_text(record["traceback"])
                raise
            record["status"] = "passed"
            summary["passed"] += 1
        assert summary["passed"] == MAX_SCENARIOS
        summary["status"] = "passed"
    except Exception as exc:
        summary["error"] = str(exc)
        summary["traceback"] = traceback.format_exc()
        traceback.print_exc(file=sys.stderr)
    finally:
        summary["executed"] = len(summary["scenarios"])
        if artifact_dir is not None:
            (artifact_dir / "research-summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, sort_keys=True), flush=True)
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
