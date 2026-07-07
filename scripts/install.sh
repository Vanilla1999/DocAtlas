#!/usr/bin/env sh
# DocAtlas one-line installer.
#
#   curl -LsSf https://raw.githubusercontent.com/Vanilla1999/DocAtlas/main/scripts/install.sh | sh
#
# Installs uv (if missing), installs the `doc-atlas` CLI, and registers the
# DocAtlas docs MCP server (`doc-atlas mcp docs-serve`) into the AI agent(s) you
# choose: Claude Code, OpenCode, and/or Codex.
#
# Agent selection (first source that is set wins):
#   1. positional args:  ... | sh -s -- claude-code opencode
#   2. env var:          DOCATLAS_AGENT="codex opencode" ... | sh   (also: all / none)
#   3. interactive menu read from /dev/tty
#   4. no tty and nothing set -> skip MCP registration (prints manual steps)
set -eu

SERVER_NAME="docatlas-docs"
REPO_URL="https://github.com/Vanilla1999/DocAtlas"

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
  C_BOLD="$(printf '\033[1m')"; C_DIM="$(printf '\033[2m')"
  C_GREEN="$(printf '\033[32m')"; C_YELLOW="$(printf '\033[33m')"
  C_RED="$(printf '\033[31m')"; C_RESET="$(printf '\033[0m')"
else
  C_BOLD=""; C_DIM=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_RESET=""
fi

info() { printf '%s==>%s %s\n' "$C_BOLD" "$C_RESET" "$*"; }
ok()   { printf '%s  ok%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '%swarn%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
die()  { printf '%serror%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; exit 1; }
step() { printf '%s%s%s\n' "$C_DIM" "$*" "$C_RESET"; }

have() { command -v "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------------------
# A. Environment
# ---------------------------------------------------------------------------
have curl || die "curl is required. Install curl and re-run, or install manually: uv tool install doc-atlas"

OS="$(uname -s 2>/dev/null || echo unknown)"
case "$OS" in
  Linux|Darwin) : ;;
  *) die "This installer supports macOS and Linux only (detected: $OS). Manual install: see $REPO_URL#installation" ;;
esac

# ---------------------------------------------------------------------------
# B. uv
# ---------------------------------------------------------------------------
ensure_path() {
  # Make uv-managed bins visible in this process for the rest of the run.
  for d in "$HOME/.local/bin" "$HOME/.cargo/bin"; do
    case ":$PATH:" in
      *":$d:"*) : ;;
      *) [ -d "$d" ] && PATH="$d:$PATH" ;;
    esac
  done
  export PATH
}

ensure_path
if have uv; then
  ok "uv already installed ($(uv --version 2>/dev/null || echo unknown))"
else
  info "Installing uv (Astral)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ensure_path
  have uv || die "uv installation finished but 'uv' is not on PATH. Add \$HOME/.local/bin to your PATH and re-run."
  ok "uv installed"
  step "Tip: add \$HOME/.local/bin to your shell profile PATH to keep uv/doc-atlas available."
fi

# ---------------------------------------------------------------------------
# C. doc-atlas
# ---------------------------------------------------------------------------
info "Installing doc-atlas..."
uv tool install --upgrade doc-atlas
ensure_path
have doc-atlas || die "doc-atlas was installed but is not on PATH. Ensure \$HOME/.local/bin is on PATH and re-run."
ok "doc-atlas $(doc-atlas --version 2>/dev/null || echo installed)"

# ---------------------------------------------------------------------------
# D. Agent selection
# ---------------------------------------------------------------------------
KNOWN_AGENTS="claude-code opencode codex"

# Normalize a raw selection (numbers, names, csv) into a clean agent list.
normalize_selection() {
  raw="$(printf '%s' "$1" | tr 'A-Z,' 'a-z ')"
  out=""
  for tok in $raw; do
    case "$tok" in
      1|claude|claude-code|claudecode) a="claude-code" ;;
      2|opencode|open-code)            a="opencode" ;;
      3|codex)                         a="codex" ;;
      4|all)                           a="$KNOWN_AGENTS" ;;
      5|skip|none|no)                  a="" ;;
      *) warn "Unknown agent '$tok' (ignored). Valid: claude-code, opencode, codex, all, none"; continue ;;
    esac
    for one in $a; do
      case " $out " in *" $one "*) : ;; *) out="$out $one" ;; esac
    done
  done
  printf '%s' "${out# }"
}

SELECTION=""
SELECTION_SOURCE=""
if [ "$#" -gt 0 ]; then
  SELECTION="$(normalize_selection "$*")"; SELECTION_SOURCE="arguments"
elif [ -n "${DOCATLAS_AGENT:-}" ]; then
  SELECTION="$(normalize_selection "$DOCATLAS_AGENT")"; SELECTION_SOURCE="\$DOCATLAS_AGENT"
elif [ -r /dev/tty ]; then
  printf '\n%sRegister the DocAtlas docs MCP server into which agent(s)?%s\n' "$C_BOLD" "$C_RESET"
  printf '  1) claude-code\n  2) opencode\n  3) codex\n  4) all\n  5) skip\n'
  printf 'Enter number(s) or name(s), space-separated [5]: '
  reply=""; IFS= read -r reply </dev/tty || reply=""
  [ -z "$reply" ] && reply="skip"
  SELECTION="$(normalize_selection "$reply")"; SELECTION_SOURCE="prompt"
else
  warn "Non-interactive run and no agent selected; skipping MCP registration."
  step "Re-run with:  DOCATLAS_AGENT=claude-code  (or: opencode / codex / all)"
fi

# ---------------------------------------------------------------------------
# E. MCP registration
# ---------------------------------------------------------------------------
pick_python() {
  if have python3; then printf 'python3'
  elif have python; then printf 'python'
  else printf 'uv run --no-project python'
  fi
}

register_claude_code() {
  if ! have claude; then
    warn "claude CLI not found; skipping Claude Code registration."
    step "Add manually later:  claude mcp add --scope user $SERVER_NAME -- doc-atlas mcp docs-serve"
    return 0
  fi
  if claude mcp get "$SERVER_NAME" >/dev/null 2>&1; then
    ok "claude-code: '$SERVER_NAME' already registered"
    return 0
  fi
  if claude mcp add --scope user "$SERVER_NAME" -- doc-atlas mcp docs-serve; then
    ok "claude-code: registered '$SERVER_NAME'"
  else
    warn "claude-code: 'claude mcp add' failed; add manually: claude mcp add --scope user $SERVER_NAME -- doc-atlas mcp docs-serve"
  fi
}

register_codex() {
  cfg="$HOME/.codex/config.toml"
  # Prefer the official Codex CLI, which manages the config for us.
  if have codex; then
    if codex mcp get "$SERVER_NAME" >/dev/null 2>&1; then
      ok "codex: '$SERVER_NAME' already registered"
      return 0
    fi
    if codex mcp add "$SERVER_NAME" -- doc-atlas mcp docs-serve; then
      ok "codex: registered '$SERVER_NAME'"
      return 0
    fi
    warn "codex: 'codex mcp add' failed; falling back to direct config edit."
  fi
  mkdir -p "$(dirname "$cfg")"
  [ -f "$cfg" ] || : >"$cfg"
  # Match both bare and quoted TOML section headers, ignoring inner whitespace.
  if grep -Eq "^\[mcp_servers\.(\"$SERVER_NAME\"|$SERVER_NAME)\][[:space:]]*$" "$cfg" 2>/dev/null; then
    ok "codex: '$SERVER_NAME' already present in $cfg"
    return 0
  fi
  cp "$cfg" "$cfg.bak" 2>/dev/null || true
  # Ensure a separating newline before appending our block.
  [ -s "$cfg" ] && printf '\n' >>"$cfg"
  {
    printf '[mcp_servers.%s]\n' "$SERVER_NAME"
    printf 'command = "doc-atlas"\n'
    printf 'args = ["mcp", "docs-serve"]\n'
  } >>"$cfg"
  ok "codex: registered '$SERVER_NAME' in $cfg (backup: $cfg.bak)"
}

register_opencode() {
  cfg="$HOME/.config/opencode/opencode.json"
  mkdir -p "$(dirname "$cfg")"
  PY="$(pick_python)"
  if OPENCODE_CFG="$cfg" SERVER_NAME="$SERVER_NAME" $PY - <<'PY'
import json, os, shutil, sys

path = os.environ["OPENCODE_CFG"]
name = os.environ["SERVER_NAME"]

data = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read().strip()
    if text:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            print(f"opencode config is not valid JSON: {exc}", file=sys.stderr)
            sys.exit(2)
    if not isinstance(data, dict):
        print("opencode config must be a JSON object", file=sys.stderr)
        sys.exit(2)

servers = data.setdefault("mcp", {})
if not isinstance(servers, dict):
    print("opencode 'mcp' key must be an object", file=sys.stderr)
    sys.exit(2)

desired = {"type": "local", "command": ["doc-atlas", "mcp", "docs-serve"], "enabled": True}
if servers.get(name) == desired:
    print("unchanged")
    sys.exit(0)

if os.path.exists(path):
    shutil.copy2(path, path + ".bak")
servers[name] = {**(servers.get(name) or {}), **desired}
with open(path, "w", encoding="utf-8") as fh:
    fh.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
print("written")
PY
  then
    ok "opencode: '$SERVER_NAME' configured in $cfg"
  else
    warn "opencode: could not update $cfg automatically."
    step "Add manually under the \"mcp\" key: {\"$SERVER_NAME\": {\"type\":\"local\",\"command\":[\"doc-atlas\",\"mcp\",\"docs-serve\"],\"enabled\":true}}"
  fi
}

if [ -n "$SELECTION" ]; then
  info "Registering docs MCP for: $SELECTION  (from $SELECTION_SOURCE)"
  for agent in $SELECTION; do
    case "$agent" in
      claude-code) register_claude_code ;;
      opencode)    register_opencode ;;
      codex)       register_codex ;;
    esac
  done
fi

# ---------------------------------------------------------------------------
# F. Summary
# ---------------------------------------------------------------------------
printf '\n%sDocAtlas is ready.%s\n' "$C_GREEN$C_BOLD" "$C_RESET"
printf '  %s\n' "$(doc-atlas --version 2>/dev/null || echo 'doc-atlas installed')"
if [ -n "$SELECTION" ]; then
  case " $SELECTION " in *" claude-code "*) have claude && { printf '  MCP servers:\n'; claude mcp list 2>/dev/null | sed 's/^/    /'; } ;; esac
fi
printf '\nNext steps:\n'
printf '  doc-atlas setup\n'
printf '  doc-atlas query "how to authenticate"\n'
printf '  doc-atlas mcp docs-serve      # run the docs MCP server\n'
printf '\nDocs: %s\n' "$REPO_URL"
