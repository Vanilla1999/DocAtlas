# Isolated SQLite native research spike — NOT production persistence

Base: `cb29039e`. Only the approved experimental files and new test/label shard
are involved. No production imports, dispatch, agents, config, build packaging,
installation, live indexes, providers, or catalog changes. D1 stays unchanged.
No agents were delegated. R1 is OPEN. Object-bound grant semantics are NOT
approved; this spike observes their consequences, rather than adopting them.

## What is implemented

An existing compiler builds one experimental shared object into a disposable
`/tmp/opencode` fixture directory. Python loads it into a fresh RAM connection;
`SQLITE_EXTENSION_INIT2(pApi)` supplies the exact built-in SQLite API table.
There is no `libsqlite3` link, runtime compiler/download, new dependency,
CPython-private pointer access, or generic broker. The extension returns
`SQLITE_OK_LOAD_PERMANENTLY` so registered VFS/syscall callbacks cannot outlive
their code within the disposable worker. The loader stays alive until
the experimental target connection closes. Extension loading is disabled
immediately after loading the fixture-author artifact.

The separately executed worker has a finite protocol: profile, one README
upsert, recovery observation, or predetermined denial probes. Requests are
limited to 8192 characters; initial DB/journal sizes to 4 MiB; the descriptor
registry to 128 slots. Native target I/O recognizes only two synthetic names:
`/spike/main` and `/spike/main-journal`. Three inherited descriptors select the
DB, **pre-created** journal, and directory. There is no pathname open fallback,
`/proc` alias, sidecar creation, cleanup, or automatic bootstrap. Stdin/stdout
checkpoints and SPIKE_* faults exist solely for deterministic fixture attacks.

The worker validates the exact observed runtime profile, configures connection-
local `locking_mode=EXCLUSIVE`, `journal_mode=PERSIST`, `temp_store=MEMORY`,
`mmap_size=0`, `synchronous=FULL`, and executes `BEGIN EXCLUSIVE`. C traces
verify successful lock level 4; native data writes require that state. Generation
CAS and the fixture member-owner check occur in the same SQLite transaction.
This exercises a small fixture schema, **not** production member SQL/retrieval.

An initial experiment exposed ignored fchmod errors and a denied journal delete
on close in DELETE mode. No unsafe unlink was implemented. PERSIST avoids that
normal close route, and native denials poison later writes and invalidate even
an apparently successful close. R's independent audit of `a7a41ac5` found that
actual close EIO was still false-green: SQLite's `robust_close()` discards the
return code, and the old test directly poisoned status in the fault itself.
The followup instead independently latches every observed close syscall failure
and errno. The EIO fault primitive closes the FD then returns -1/EIO without
touching denial/latch state; the observer must catch it. DB, journal and directory
close cases are exercised. No close retries occur. A final DB close failure after
commit invalidates success even with **zero native denials**; outcome is unknown,
not zero mutation. Close outcomes and SQLite xClose outcomes are traced separately.

Write events are explicitly `db_write_attempt` / `journal_write_attempt`.
Each is followed by `write_syscall_result` with requested/result bytes, errno and
whether the syscall ran, including denied attempts. These results indicate kernel
acceptance, NOT storage durability. `io_evidence` no longer claims physical writes.

## Measured runtime, not an optional-API assumption

Python: 3.13.12; built-in SQLite: 3.50.4.

SQLite source ID:

```text
2025-07-30 19:33:53 4d8adfb30e03f9cf27f800a2c1ba3c48fb4ca1b08b0f5ed59a4d5ecbf45e20a3
```

Actual `unix.xNextSystemCall()` profile:

```text
open,close,access,getcwd,stat,fstat,ftruncate,fcntl,read,pread,write,pwrite,fchmod,unlink,openDirectory,mkdir,rmdir,fchown,geteuid,mmap,munmap,mremap,getpagesize,readlink,lstat
```

All 25 available hooks are replaced and individually traced **on this trusted
profile only; hook coverage is not confinement**. Absent hooks in
the source table: `pread64`, `pwrite64`, `fallocate`, `ioctl`. Unknown hooks reject
binding. The complete measured `PRAGMA compile_options` is pinned in `worker.py`
and emitted into profile artifacts; a different profile rejects target access.
It includes `THREADSAFE=1`, `TEMP_STORE=1`, `DEFAULT_AUTOVACUUM`,
`DEFAULT_MMAP_SIZE=0`, `MAX_MMAP_SIZE=0x7fff0000`, and clang-22.1.1. Pinning this
profile is an experimental restriction, not a portable runtime support policy.

### Source audit / coverage map

Inspected exact 3.50.4 sources:

- https://raw.githubusercontent.com/sqlite/sqlite/version-3.50.4/src/os_unix.c
- https://raw.githubusercontent.com/sqlite/sqlite/version-3.50.4/src/pager.c
- https://raw.githubusercontent.com/sqlite/sqlite/version-3.50.4/src/pragma.c

Fetched source SHA256 pins (not compiled or vendored):

```text
os_unix.c  4f2799675dd370a79d501d1be830a5a33ad4cff5fffa9cef3cb3b24b0bc80dd3
pager.c    0936a093b301cfadcf34d384698fe7eb34e507239d400572f73e8cd12ef88939
pragma.c   6c152895b2e85b9fa855891b199df8d57184ae6772c5eb682c0b0cd32d455b74
```

| Source route | Treatment |
|---|---|
| `unixOpen` / `robust_open`, reusable-FD stat | Exact synthetic names map to duplicates of retained descriptors; no real path is opened. Destructive open flags deny. |
| stat/lstat/access/readlink/getcwd | Retained-object stat only; unknown paths and path discovery deny. |
| `unixDelete`, unlink/rmdir/mkdir | Deny; never translate into unsafe unlink or pretend deletion succeeded. |
| `unixSync` / `openDirectory` | Duplicated inherited directory FD; base Unix sync methods retained. |
| direct fsync/fdatasync in `full_fsync` | Not in xSetSystemCall table. They receive the selected file or directory FD; xSync entry/result is traced. Injected faults are at xSync, NOT actual kernel/hardware fsync faults. |
| fcntl locking / Unix inode registry / close deferral | Original POSIX protocol on retained-inode duplicates, with command/type/byte-range traces. Worker has no inherited SQLite connection. Extra retained FDs close only after its target connection exits. |
| `robust_close` / raw close | Actual syscall return/errno latched independently; default VFS may report OK despite raw close EIO. No retries or false-success inference from xClose. |
| pread/read/fstat, pwrite/write/ftruncate | Registered FDs only. Writes require successful exclusive lock; link-count detector is explicitly non-atomic. |
| permission/ownership adjustment | Deny and poison context, including adjustments SQLite might otherwise ignore. |
| mmap/munmap/mremap, xShmMap/Lock/Unmap | Deny; unexpected xShmBarrier terminates worker. Database xFetch is not supplied. |
| `unixOpenSharedMemory` | **Not covered by an xOpen-only shim.** WAL is rejected by header before target open; SHM callbacks deny and syscall open has no SHM mapping. No normal/shared WAL success claim. |
| rollback `pager_end_transaction` | PERSIST zeroes the journal header through retained FD; no ad hoc journal finalization. |
| other cleanup/recovery deletes | Deny. Any observed denial invalidates the result. Not all pager branches have been exercised. |
| temporary/attached/super-journal file kinds | Deny; temp_store is RAM, and the finite worker never accepts SQL. |
| xDlOpen | Initial artifact loading uses the original VFS before interception. Target VFS denies additional loading; SQL extension loading remains disabled. |
| geteuid/getpagesize | Side-effect-free OS queries. |
| platform-specific direct fstatfs/locking/atomic ioctl branches | Not a portability claim: the pinned Linux Unix profile is required; other builds are unsupported. |

Known rollback-only WAL/SHM existence probes return absent without opening those
paths. They are not a general unknown-path success response. Runtime hook/source
IDs do not authenticate a maliciously modified SQLite binary; trusted runtime
code is an experimental assumption. No syscall tracing tool or binary-wide
proof of absence of every direct OS call has been obtained.

## Header provenance and license

Headers originate from the official, reviewed 3.50.4 amalgamation:
https://www.sqlite.org/2025/sqlite-amalgamation-3500400.zip

```text
archive SHA256: 1d3049dd0f830a025a53105fc79fd2ab9431aea99e137809d064d8ee8356b032
sqlite3.h:     abd1514e0351f79393d1be882830afdb40a8099e8257f311f0bfdf8486f11bea
sqlite3ext.h upstream:   9a91de0d5e5ccc04ec59041275c67972d6f8894f7543a10033e387b69987beb5
sqlite3ext.h normalized: 6a1a5763c6293fa3599ad4ef851d03057176fae49b7c50deafe193cf438c7d61
```

SQLite is public domain (https://www.sqlite.org/copyright.html); upstream header
notices are retained. Our experimental C/Python follow the repository MIT license.
The amalgamation implementation is not bundled or compiled. The standalone
runner and portable tests verify header hashes locally; neither they nor the
worker fetch headers.
Transformation: remove exactly one trailing ASCII space immediately before LF
on `sqlite3ext.h` lines 15, 709, 716. All other bytes, including the license,
remain unchanged; `sqlite3.h` remains byte-exact. The portable test reconstructs
the three spaces and verifies the upstream SHA. The standalone runner and portable
tests check the normalized SHA against constants defined in `worker.py`; the worker
itself does not perform that hash check. Diff checks require no header exceptions.

## Reproduce — disposable fixtures only

From `/tmp/opencode/mcp-storage-a`, portable default-discovered checks (no native
build/load, compiler or SQLite-profile requirement):

```bash
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 \
PYTHONPATH=/tmp/opencode/mcp-storage-a \
/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python \
-m pytest -p no:cacheprovider -q \
--basetemp=/tmp/opencode/mcp-storage-native-spike-portable-reproduce \
tests/test_mcp_storage_native_spike.py
```

Standalone opt-in positive native research, requiring the exact trusted Linux
profile above (including built-in SQLite compiled with clang-22.1.1):

```bash
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 \
/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python \
tests/mcp_storage_native_spike_checks.py \
--artifact-dir /tmp/opencode/mcp-storage-native-spike-standalone-reproduce
```

The **16 portable pytest checks** run normal ancestor conftest/diagnostic gates.
The **27 standalone research scenarios do not**: the runner has no pytest import,
fixture/mark machinery or `test_*` functions and is not pytest inventory. Only its
newly added diagnostic label/hash were removed; no historical labels or gates
changed. It is not an active product gate being disabled. No standalone result is
ordinary Python 3.11/3.12/3.13 CI coverage or full-CI-green evidence.
CI/workflows/conftest/pytest.ini remain unchanged.

The directory-inventory conflict is resolved by the genuinely standalone evidence
contract, not a gate bypass. The portable inventory helper verifies compatible
default directory selection. Actual normal directory collection was also checked
without executing historical suites:

```bash
PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 \
PYTHONPATH=/tmp/opencode/mcp-storage-a \
/home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python \
-m pytest -p no:cacheprovider --collect-only -q tests/
```

The runner admits runtime/source/compile profile and local header hashes before
compiler lookup or creating the requested artifact directory. Unsupported runs
emit an error JSON summary and traceback, exit nonzero, and execute zero scenarios.
The CLI requires one new canonical absolute disposable directory below
`/tmp/opencode`; existing directories are never overwritten or removed. The fixed
registry contains exactly 27 parameter-expanded scenarios, each using its own
fresh fixture and a resource-cleanup context manager. No selection/filter/skip
options exist. Run without `-O`; disabled assertions are rejected.

Limits: 4 SQLite workers per scenario, 30 checkpoint records, 64 KiB pending
checkpoint output and a 5-second checkpoint deadline, 10-second worker completion
and 5-second kill waits; independent
reader/peer subprocesses have 5-second waits, compiler has 30 seconds. Worker
request/object/descriptor limits remain unchanged. On a failed scenario the runner
stops, preserves failure traceback/counts, cleans up processes/descriptors and
exits nonzero. `research-summary.json` and stdout JSON record individual outcomes,
executed/passed/failed/expected counts, `normal_pytest_gate=false`, and `R1=OPEN`.

C is built with the existing `cc` using
`-std=c11 -Wall -Wextra -Werror -Wno-misleading-indentation -fPIC -shared`.
Use fresh directories for reproduction: pytest owns portable `--basetemp`, while
the standalone runner refuses an existing `--artifact-dir`. No skips convert
unsupported positive platforms into successful coverage.

Standalone trace artifacts are `<artifact-dir>/<number>_<scenario>/worker-*.trace`
(native JSONL) and
`worker-*.stdout.jsonl` (startup/CAS/result/close JSONL). Profile artifacts:
`01_exact_profile_and_header_provenance/profile.json`. Hostile removal observation:
`25_hostile_hot_journal_removal_exposes_unresolved_crash_obligation/hostile-removal-observation.json`.
Worker stdout traces startup/CAS/commit/close; C traces hook installation, actual
locks, write attempts/results, sync results, denials, and raw/SQLite close results.
Forced exit 86 has no final
result; it must never be interpreted as a successful or zero-write operation.

The standalone scenarios demonstrate clean fixture commit/default-reader compatibility,
generation/owner denial, independent default-writer contention, two-worker CAS,
pre/post-check swaps without redirected foreign-inode writes, hardlink detection,
sync/close errors, intact hot-journal recovery, and denied unknown/SHM routes.
They also preserve negative observations: a directory rename can leave the
retained-directory operation committing outside the current pathname, and a
post-final-check replacement can leave the committed DB unreachable at its name.
Those are evidence of unresolved grant semantics, NOT success under the required
production security contract.

### Standalone evidence-contract followup validation

Measured on the reviewed Python 3.13.12 / SQLite 3.50.4 profile:

* Normally gated portable exact-file run: **16 passed**; artifacts
  `/tmp/opencode/mcp-storage-standalone-portable-final-v2/` (includes compatible
  directory-inventory observation).
* Standalone research: **27 passed**, not normally gated pytest cases; artifacts
  `/tmp/opencode/mcp-storage-standalone-positive-final-v2/`. Directories 22–24 contain
  raw DB/journal/directory close EIO and worker error/unknown outcome JSONL. DB
  final-close case includes commit-returned evidence with zero native denials.
  Close-fault, write-result and header provenance assertions are preserved. This
  run also used Python `-S` (no site-package initialization), demonstrating the
  standalone runner's lack of pytest/third-party dependency.
* Unsupported Python 3.12 standalone admission: **exit 1**, zero scenarios, no
  requested artifact directory or shared-object build; output/observation at
  `/tmp/opencode/mcp-storage-standalone-unsupported-evidence/`. This is negative
  admission evidence, not a passing positive or matrix-green claim.
* Actual normal `tests/ --collect-only`: **exit 0**, **8561 collected**, none
  executed. Output/observation at
  `/tmp/opencode/mcp-storage-standalone-directory-collection/`. This validates
  directory inventory, not historical test results or full CI.
* Repository Python module-size gate, authored Python AST checks, and
  `git diff --check` pass. Authored C, worker, portable tests and standalone runner
  remain below 1000 lines. No install, dependency or gate/config change was made.

R1 remains OPEN; independent re-audit is still required. No production persistence,
packaging, object-grant semantics, protected recovery namespace, or WAL approval
is implied by these experimental checks.

## Unresolved obligations — no threat-model weakening

1. **R1 remains OPEN.** No production persistence, prepare→retrieve, or installed
   artifact acceptance is delivered by this fixture schema.
2. **Object-bound grants are not approved.** Directory/file moves can leave the
   original descriptors usable while the granted pathname denotes other objects.
   The experiment does not authorize continued production mutation in that case.
3. **Post-pin aliases:** fstat(nlink) detects the tested checkpoint, but is not
   atomic with a subsequent write. Strict no-external-alias guarantees remain open.
4. **Crash plus hostile journal removal:** a test changes the DB, kills the worker,
   and removes exactly the disposable hot journal. The surviving recovery data
   disappears. No retained-FD scheme repairs this after process death; a protected
   recovery namespace or equivalent enforceable condition would be required.
5. **Journal pairing/restart:** existing object descriptors do not prove that
   arbitrary preexisting hot journals belong to the DB. The controlled fixture
   pairing is not an authenticated restart/provisioning contract. No inode-reuse,
   replay, rollback-resistance, or resurrection proof is claimed.
6. **WAL/SHM:** SQLite 3.50.4 has the upstream WAL-reset defect. WAL is unconditionally
   unsupported here; exclusive/shared exclusion and all WAL recovery/close paths
   have not been proved. No header conversion or automatic upgrade is performed.
7. **Durability:** ordinary intact-journal process-crash recovery is exercised;
   power-loss, real fsync failures, filesystem/hardware guarantees, and every
    error cleanup branch remain unproved. Recovery write attempts and syscall
    results are reported separately from member attempts; syscall success is not
    proof of physical durability. Unknown commits remain unknown.
8. **Same-UID direct rewriting:** descriptor binding does not protect inode contents
   from a malicious writer with equivalent credentials. No advisory-lock defense
   or filesystem permission assumption is substituted for hostile-race protection.
9. **Platforms:** positive tests target only the measured 64-bit Linux build.
   Windows/macOS implementations, packaging, compiler distribution, and installed
   trust for the native artifact require later approval; existing gates unchanged.
10. **Safety breadth:** descriptor-budget exhaustion, corruption/parser attacks,
    worker transport/cancellation limits, remaining IO branches, and source-wide
    native review require further review. This is not a generic hardened VFS.

## Fresh initialization option — design only

Latest steering removes legacy-row/format preservation and identity migration
requirements for the unused disposable DB. This spike already uses a fresh
fixture schema and no aliases. A later separately approved initializer could
create a new main DB and journal exclusively through pinned-directory operations,
validate both descriptors before handing them to this route, and retain a standard
PERSIST journal. That removes adoption/pairing ambiguity at the initial creation
boundary, but does NOT solve directory moves, late hardlinks, crash-sidecar removal,
or authenticated reopen. No such initializer, product/storage change, live-path
read/deletion, production integration, or migration is implemented here.
