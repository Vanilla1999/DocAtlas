"""Disposable-fixture research worker. Not imported by production code."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import time

MAX_REQUEST = 8192
HEADER_HASHES = {
    "sqlite3.h": "abd1514e0351f79393d1be882830afdb40a8099e8257f311f0bfdf8486f11bea",
    "sqlite3ext.h": "6a1a5763c6293fa3599ad4ef851d03057176fae49b7c50deafe193cf438c7d61",
}
# Filled from the measured built-in VFS; no generic optional-hook assumption.
EXPECTED_PROFILE = (
    "open,close,access,getcwd,stat,fstat,ftruncate,fcntl,read,pread,write,pwrite,"
    "fchmod,unlink,openDirectory,mkdir,rmdir,fchown,geteuid,mmap,munmap,mremap,"
    "getpagesize,readlink,lstat"
)
EXPECTED_COMPILE_OPTIONS = """ATOMIC_INTRINSICS=1 COMPILER=clang-22.1.1 DEFAULT_AUTOVACUUM
DEFAULT_CACHE_SIZE=-2000 DEFAULT_FILE_FORMAT=4 DEFAULT_JOURNAL_SIZE_LIMIT=-1
DEFAULT_MMAP_SIZE=0 DEFAULT_PAGE_SIZE=4096 DEFAULT_PCACHE_INITSZ=20 DEFAULT_RECURSIVE_TRIGGERS
DEFAULT_SECTOR_SIZE=4096 DEFAULT_SYNCHRONOUS=2 DEFAULT_WAL_AUTOCHECKPOINT=1000
DEFAULT_WAL_SYNCHRONOUS=2 DEFAULT_WORKER_THREADS=0 DIRECT_OVERFLOW_READ ENABLE_DBSTAT_VTAB
ENABLE_FTS3 ENABLE_FTS3_PARENTHESIS ENABLE_FTS4 ENABLE_FTS5 ENABLE_GEOPOLY ENABLE_MATH_FUNCTIONS
ENABLE_RTREE MALLOC_SOFT_LIMIT=1024 MAX_ATTACHED=10 MAX_COLUMN=2000 MAX_COMPOUND_SELECT=500
MAX_DEFAULT_PAGE_SIZE=8192 MAX_EXPR_DEPTH=1000 MAX_FUNCTION_ARG=1000 MAX_LENGTH=1000000000
MAX_LIKE_PATTERN_LENGTH=50000 MAX_MMAP_SIZE=0x7fff0000 MAX_PAGE_COUNT=0xfffffffe MAX_PAGE_SIZE=65536
MAX_SQL_LENGTH=1000000000 MAX_TRIGGER_DEPTH=1000 MAX_VARIABLE_NUMBER=32766 MAX_VDBE_OP=250000000
MAX_WORKER_THREADS=8 MUTEX_PTHREADS SYSTEM_MALLOC TEMP_STORE=1 THREADSAFE=1""".split()
EXPECTED_SOURCE_ID = "2025-07-30 19:33:53 4d8adfb30e03f9cf27f800a2c1ba3c48fb4ca1b08b0f5ed59a4d5ecbf45e20a3"


def validate_profile(profile, identity, options):
    """Pure admission check; never infer support from an optional API alone."""
    if profile != EXPECTED_PROFILE:
        raise PermissionError("unsupported exact Unix syscall profile")
    if options != EXPECTED_COMPILE_OPTIONS:
        raise PermissionError("unsupported exact SQLite compile profile")
    if identity != ("3.50.4", EXPECTED_SOURCE_ID):
        raise PermissionError("unsupported SQLite source identity")


def validate_request(raw):
    if len(raw) > MAX_REQUEST:
        raise ValueError("fixture request too large")
    request = json.loads(raw)
    if not isinstance(request, dict) or set(request) - {
        "operation", "expected_generation", "new_generation", "content", "pause",
    } or request.get("operation") not in {"profile", "upsert", "recover", "probe_denials"}:
        raise ValueError("invalid finite fixture request")
    if request["operation"] != "profile":
        if any(type(request.get(key)) is not str for key in ("expected_generation", "new_generation", "content")):
            raise ValueError("explicit fixture generation and member bytes required")
        if request.get("pause") not in {None, "bound", "locked", "before_commit"}:
            raise ValueError("unknown fixture checkpoint")
    return request


def emit(value):
    print(json.dumps(value, sort_keys=True), flush=True)


def checkpoint(request, phase):
    if request.get("pause") == phase:
        emit({"checkpoint": phase})
        if sys.stdin.readline(32) != "continue\n":
            raise PermissionError("invalid fixture continuation")


def namespace_matches(directory, database, journal):
    for name, fd in (("index.db", database), ("index.db-journal", journal)):
        current = os.stat(name, dir_fd=directory, follow_symlinks=False)
        selected = os.fstat(fd)
        if (current.st_dev, current.st_ino) != (selected.st_dev, selected.st_ino):
            raise PermissionError("fixture namespace replaced")


def run(args, request):
    loader = sqlite3.connect(":memory:")
    conn = None
    attempts = False
    committed = False
    profile = None
    outcome = {}
    started = time.monotonic()
    # These markers do not prove physical zero writes; stderr is the evidence.
    try:
        if sys.platform != "linux" or not hasattr(loader, "enable_load_extension"):
            raise PermissionError("unsupported spike platform")
        if not args.extension.is_absolute():
            raise PermissionError("extension must be a fixture-author absolute artifact")
        loader.enable_load_extension(True)
        try:
            loader.load_extension(str(args.extension))
        finally:
            loader.enable_load_extension(False)
        profile = loader.execute("SELECT spike_profile()").fetchone()[0]
        identity = loader.execute("SELECT sqlite_version(), sqlite_source_id()").fetchone()
        options = [row[0] for row in loader.execute("PRAGMA compile_options")]
        emit({"profile": profile, "sqlite_version": identity[0], "sqlite_source_id": identity[1],
              "compile_options": options})
        if request["operation"] == "profile":
            return {"status": "profile", "profile": profile}
        validate_profile(profile, identity, options)
        for fd in (args.database_fd, args.journal_fd, args.directory_fd):
            os.fstat(fd)
        if not stat.S_ISDIR(os.fstat(args.directory_fd).st_mode):
            raise PermissionError("invalid fixture directory")
        namespace_matches(args.directory_fd, args.database_fd, args.journal_fd)
        loader.execute("SELECT spike_bind(?,?,?)", (args.database_fd, args.journal_fd, args.directory_fd)).fetchone()
        if request["operation"] == "probe_denials":
            outcome.update(status="error", probe_denials=loader.execute("SELECT spike_probes()").fetchone()[0])
            return outcome
        checkpoint(request, "bound")
        conn = sqlite3.connect("file:/spike/main?vfs=docatlas_spike&mode=rw", uri=True, timeout=0.15)
        conn.execute("PRAGMA locking_mode=EXCLUSIVE")
        if conn.execute("PRAGMA journal_mode=PERSIST").fetchone()[0] != "persist":
            raise PermissionError("persist rollback mode unavailable")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=0")
        conn.execute("PRAGMA synchronous=FULL")
        emit({"phase": "begin_exclusive"})
        conn.execute("BEGIN EXCLUSIVE")
        # The C trace must demonstrate lock level 4; a pragma alone is not proof.
        checkpoint(request, "locked")
        namespace_matches(args.directory_fd, args.database_fd, args.journal_fd)
        generation = conn.execute("SELECT generation FROM index_state WHERE id=1").fetchone()[0]
        if generation != request["expected_generation"]:
            raise ValueError("stale generation")
        owner = conn.execute("SELECT owner FROM members WHERE path='README.md'").fetchone()
        if owner is not None and owner[0] != "fixture-owner":
            raise PermissionError("member ownership conflict")
        emit({"phase": "cas_passed", "generation": generation})
        if loader.execute("SELECT spike_status(), spike_close_errors()").fetchone() != (0, 0):
            raise PermissionError("native denial or close failure before member writes")
        if request["operation"] == "recover":
            conn.rollback()
            outcome.update(status="recovered", generation=generation,
                           io_evidence="attempts_and_syscall_results_not_durability")
            return outcome
        attempts = True
        conn.execute("INSERT INTO members(path,owner,content) VALUES('README.md','fixture-owner',?) "
                     "ON CONFLICT(path) DO UPDATE SET content=excluded.content", (request["content"],))
        conn.execute("UPDATE index_state SET generation=? WHERE id=1", (request["new_generation"],))
        checkpoint(request, "before_commit")
        conn.commit()
        committed = True
        emit({"phase": "commit_returned"})
        outcome.update(status="experimental_commit", generation=request["new_generation"],
                       production_ready=False, io_evidence="attempts_and_syscall_results_not_durability")
        return outcome
    except Exception as exc:
        rollback = "not_needed"
        if conn is not None and conn.in_transaction:
            try:
                conn.rollback()
                rollback = "returned"
            except Exception as failure:
                rollback = type(failure).__name__ + ": " + str(failure)
        outcome.update(status="error", error=str(exc), rollback=rollback,
                       commit_outcome="unknown" if attempts or committed else "no_member_write_attempt",
                       io_evidence="attempts_and_syscall_results_not_durability", profile=profile)
        return outcome
    finally:
        if conn is not None:
            emit({"phase": "close_start"})
            try:
                conn.close()
            except Exception as exc:
                outcome.update(status="error", error="close failure: " + str(exc), commit_outcome="unknown")
            emit({"phase": "close_returned"})
        if bound_status := (loader.execute("SELECT spike_status()").fetchone()[0] if profile else 0):
            outcome.update(status="error", native_denials=bound_status,
                           commit_outcome="unknown" if attempts or committed else "no_member_write_attempt")
        if profile:
            errors, error_number = loader.execute("SELECT spike_close_errors(), spike_close_errno()").fetchone()
            if errors:
                outcome.update(status="error", error="native close syscall failed",
                               close_errors=errors, close_errno=error_number,
                               native_denials=bound_status, commit_outcome="unknown")
        loader.close()
        emit({"elapsed_seconds": round(time.monotonic() - started, 4)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--extension", type=Path, required=True)
    parser.add_argument("--database-fd", type=int, default=-1)
    parser.add_argument("--journal-fd", type=int, default=-1)
    parser.add_argument("--directory-fd", type=int, default=-1)
    args = parser.parse_args()
    raw = sys.stdin.readline(MAX_REQUEST + 1)
    request = validate_request(raw)
    emit({"result": run(args, request)})


if __name__ == "__main__":
    main()
