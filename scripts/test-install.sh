#!/usr/bin/env sh
# Smoke tests for scripts/install.sh.
#
# Runs a POSIX syntax check plus isolated end-to-end runs against stubbed
# `uv`, `doc-atlas`, `claude`, and `codex` commands in a throwaway $PATH and
# $HOME, so no network access or real installs happen. Also guards against
# hidden/bidirectional Unicode and stale installer URLs in shipped files.
set -eu

REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
INSTALL_SH="$REPO_ROOT/scripts/install.sh"

pass() { printf 'ok   %s\n' "$*"; }
fail() { printf 'FAIL %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Static checks
# ---------------------------------------------------------------------------
sh -n "$INSTALL_SH" && pass "sh -n scripts/install.sh (POSIX syntax)"

# No hidden/bidirectional Unicode or stray control chars in shipped text files.
python3 - "$REPO_ROOT" <<'PY' || fail "hidden/bidirectional Unicode or control chars found"
import sys, pathlib, unicodedata
root = pathlib.Path(sys.argv[1])
BAD = set()
for cp in list(range(0x200E, 0x2010)) + list(range(0x202A, 0x2030)) + \
          list(range(0x2066, 0x206A)) + [0x00AD, 0xFEFF, 0x200B, 0x200C, 0x200D]:
    BAD.add(cp)
bad = []
for pat in ("*.sh", "*.md", "*.toml", "*.py"):
    for f in root.rglob(pat):
        if ".git" in f.parts:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, ch in enumerate(text):
            o = ord(ch)
            if o in BAD or (o < 0x20 and ch not in "\t\n") or o == 0x7f or \
               unicodedata.category(ch) == "Cf":
                bad.append(f"{f}:char{i} U+{o:04X}")
if bad:
    print("\n".join(bad), file=sys.stderr)
    sys.exit(1)
PY
pass "no hidden/bidirectional Unicode in *.sh/*.md/*.toml/*.py"

# Installer URLs in docs/header must point at the real path (scripts/install.sh).
if grep -RnE 'raw\.githubusercontent\.com/[^ ]*/main/install\.sh' \
     "$REPO_ROOT/README.md" "$REPO_ROOT/docs" "$INSTALL_SH" 2>/dev/null; then
  fail "found stale installer URL (/main/install.sh); expected /main/scripts/install.sh"
fi
pass "installer URLs point at scripts/install.sh"

# ---------------------------------------------------------------------------
# 2. Stub harness
# ---------------------------------------------------------------------------
STUB_ROOT="$(mktemp -d)"
BIN="$STUB_ROOT/bin"
mkdir -p "$BIN"
CALL_LOG="$STUB_ROOT/calls.log"
: >"$CALL_LOG"

mkstub() { # $1 = name, stdin = body
  dest="$BIN/$1"
  cat >"$dest"
  chmod +x "$dest"
}

mkstub uv <<STUB
#!/usr/bin/env sh
echo "uv \$*" >>"$CALL_LOG"
case "\$1" in
  --version) echo "uv 0.0.0-stub" ;;
  *) : ;;
esac
STUB

mkstub doc-atlas <<STUB
#!/usr/bin/env sh
echo "doc-atlas \$*" >>"$CALL_LOG"
case "\$1" in
  --version) echo "doc-atlas 0.0.0-stub" ;;
  *) : ;;
esac
STUB

mkstub claude <<STUB
#!/usr/bin/env sh
echo "claude \$*" >>"$CALL_LOG"
case "\$2" in
  get)  exit 1 ;;   # not registered yet -> proceed to add
  add)  exit 0 ;;
  list) echo "docatlas-docs: doc-atlas mcp docs-serve" ;;
esac
exit 0
STUB

mkstub codex <<STUB
#!/usr/bin/env sh
echo "codex \$*" >>"$CALL_LOG"
case "\$2" in
  get) exit 1 ;;    # not registered yet -> proceed to add
  add) exit 0 ;;
esac
exit 0
STUB

run_install() { # remaining args passed to install.sh; runs with clean HOME
  H="$(mktemp -d)"
  : >"$CALL_LOG"
  env -i HOME="$H" PATH="$BIN:/usr/bin:/bin" \
      ${DOCATLAS_AGENT:+DOCATLAS_AGENT="$DOCATLAS_AGENT"} \
      sh "$INSTALL_SH" "$@" >"$STUB_ROOT/out.log" 2>&1
  rc=$?
  RUN_HOME="$H"
  return $rc
}

# ---------------------------------------------------------------------------
# 3. Cases
# ---------------------------------------------------------------------------

# none -> succeeds, registers nothing
run_install none || fail "install.sh none exited $?"
grep -q "claude mcp add" "$CALL_LOG" && fail "'none' should not register any agent"
pass "agent 'none': no registration"

# claude-code -> official CLI add with --scope user
run_install claude-code || fail "install.sh claude-code exited $?"
grep -q "claude mcp add --scope user docatlas-docs" "$CALL_LOG" \
  || fail "claude-code: expected 'claude mcp add --scope user'"
pass "agent 'claude-code': registered via 'claude mcp add --scope user'"

# codex (CLI present) -> official codex mcp add, no TOML file written
run_install codex || fail "install.sh codex exited $?"
grep -q "codex mcp add docatlas-docs" "$CALL_LOG" \
  || fail "codex: expected 'codex mcp add'"
[ -f "$RUN_HOME/.codex/config.toml" ] && fail "codex CLI path must not write config.toml"
pass "agent 'codex' (CLI present): registered via 'codex mcp add'"

# codex fallback (no codex CLI) -> direct TOML, idempotent on re-run
CODEX_BIN="$BIN/codex"; mv "$CODEX_BIN" "$CODEX_BIN.hidden"
run_install codex || fail "install.sh codex (fallback) exited $?"
grep -q '^\[mcp_servers\.docatlas-docs\]' "$RUN_HOME/.codex/config.toml" \
  || fail "codex fallback: TOML section not written"
# re-run against the same HOME must be a no-op (no duplicate section)
env -i HOME="$RUN_HOME" PATH="$BIN:/usr/bin:/bin" sh "$INSTALL_SH" codex >/dev/null 2>&1 \
  || fail "codex fallback re-run exited non-zero"
n="$(grep -c '^\[mcp_servers\.docatlas-docs\]' "$RUN_HOME/.codex/config.toml")"
[ "$n" -eq 1 ] || fail "codex fallback: duplicate section on re-run (count=$n)"
mv "$CODEX_BIN.hidden" "$CODEX_BIN"
pass "agent 'codex' (fallback): idempotent direct TOML write"

# opencode via DOCATLAS_AGENT env -> merges JSON config
DOCATLAS_AGENT=opencode run_install || fail "install.sh DOCATLAS_AGENT=opencode exited $?"
CFG="$RUN_HOME/.config/opencode/opencode.json"
[ -f "$CFG" ] || fail "opencode: config.json not written"
python3 - "$CFG" <<'PY' || fail "opencode: config content mismatch"
import json, sys
d = json.load(open(sys.argv[1]))
srv = d["mcp"]["docatlas-docs"]
assert srv == {"type": "local", "command": ["doc-atlas", "mcp", "docs-serve"], "enabled": True}, srv
PY
pass "agent 'opencode' (via env): JSON config merged"

# opencode with a custom OPENCODE_CONFIG path -> writes there, not the default
H="$(mktemp -d)"; CUSTOM="$H/custom/oc.json"
env -i HOME="$H" PATH="$BIN:/usr/bin:/bin" OPENCODE_CONFIG="$CUSTOM" \
    sh "$INSTALL_SH" opencode >/dev/null 2>&1 || fail "opencode OPENCODE_CONFIG run failed"
[ -f "$CUSTOM" ] || fail "opencode: OPENCODE_CONFIG path not honored"
[ -f "$H/.config/opencode/opencode.json" ] && fail "opencode: wrote default path despite OPENCODE_CONFIG"
pass "agent 'opencode': OPENCODE_CONFIG custom path honored"

# OPENCODE_CONFIG_DIR is not an OpenCode config-file override; do not write
# $OPENCODE_CONFIG_DIR/opencode.json unless OPENCODE_CONFIG points there.
H="$(mktemp -d)"; OCD="$H/opencode-dir"
env -i HOME="$H" PATH="$BIN:/usr/bin:/bin" OPENCODE_CONFIG_DIR="$OCD" \
    sh "$INSTALL_SH" opencode >/dev/null 2>&1 || fail "opencode OPENCODE_CONFIG_DIR run failed"
[ ! -f "$OCD/opencode.json" ] || fail "opencode: OPENCODE_CONFIG_DIR should not be treated as config file location"
[ -f "$H/.config/opencode/opencode.json" ] || fail "opencode: default config not written when only OPENCODE_CONFIG_DIR is set"
pass "agent 'opencode': OPENCODE_CONFIG_DIR is ignored for config-file path"

# README pipe forms should work when the script is read from stdin.
H="$(mktemp -d)"; : >"$CALL_LOG"
cat "$INSTALL_SH" | env -i HOME="$H" PATH="$BIN:/usr/bin:/bin" DOCATLAS_AGENT=opencode sh \
    >/dev/null 2>&1 || fail "pipe form with DOCATLAS_AGENT=opencode failed"
[ -f "$H/.config/opencode/opencode.json" ] || fail "pipe env form: opencode config not written"
pass "README pipe form: cat scripts/install.sh | DOCATLAS_AGENT=opencode sh"

H="$(mktemp -d)"; : >"$CALL_LOG"
cat "$INSTALL_SH" | env -i HOME="$H" PATH="$BIN:/usr/bin:/bin" sh -s -- claude-code opencode \
    >/dev/null 2>&1 || fail "pipe form with positional agents failed"
grep -q "claude mcp add --scope user docatlas-docs" "$CALL_LOG" \
  || fail "pipe positional form: expected claude registration"
[ -f "$H/.config/opencode/opencode.json" ] || fail "pipe positional form: opencode config not written"
pass "README pipe form: cat scripts/install.sh | sh -s -- claude-code opencode"

# opencode with an existing JSONC config (comments + trailing comma) -> merged,
# existing keys preserved, comments dropped on rewrite
H="$(mktemp -d)"; JC="$H/oc.jsonc"
cat >"$JC" <<'JSONC'
{
  // user theme
  "theme": "dark",
  "mcp": {
    "other": { "type": "local", "command": ["x"], "enabled": true },
  },
}
JSONC
env -i HOME="$H" PATH="$BIN:/usr/bin:/bin" OPENCODE_CONFIG="$JC" \
    sh "$INSTALL_SH" opencode >/dev/null 2>&1 || fail "opencode JSONC run failed"
python3 - "$JC" <<'PY' || fail "opencode: JSONC merge/preservation mismatch"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["theme"] == "dark", d
assert d["mcp"]["other"] == {"type": "local", "command": ["x"], "enabled": True}, d
assert d["mcp"]["docatlas-docs"] == {"type": "local", "command": ["doc-atlas", "mcp", "docs-serve"], "enabled": True}, d
PY
[ -f "$JC.bak" ] || fail "opencode: JSONC rewrite did not keep a .bak"
pass "agent 'opencode': JSONC parsed, existing keys preserved, .bak kept"

# unknown explicit agent (positional) -> hard failure
if run_install codx 2>/dev/null; then
  fail "unknown positional agent 'codx' should fail, but exited 0"
fi
pass "unknown positional agent 'codx': strict failure"

# unknown explicit agent (env) -> hard failure
if DOCATLAS_AGENT=claud-code run_install 2>/dev/null; then
  fail "unknown DOCATLAS_AGENT 'claud-code' should fail, but exited 0"
fi
pass "unknown env agent 'claud-code': strict failure"

rm -rf "$STUB_ROOT"
printf '\nAll installer smoke tests passed.\n'
