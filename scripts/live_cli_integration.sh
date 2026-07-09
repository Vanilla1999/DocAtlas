#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$ROOT_DIR/.." && pwd)"

# Command to run a quick smoke test: DOCMANCER_RUN_FETCH_STEP=0 DOCMANCER_RUN_GITHUB_BLOB=0 DOCMANCER_LIVE_MAX_PAGES=1 scripts/live_cli_integration.sh

# Mirror all stdout/stderr to a log file while keeping the console. Default path is
# scripts/live_cli_integration_YYYYMMDD_HHMMSS.log. Override with DOCMANCER_LIVE_LOG_FILE.
# Set DOCMANCER_LIVE_NO_LOG=1 to skip the log file (terminal only).
LOG_FILE=""
if [[ "${DOCMANCER_LIVE_NO_LOG:-0}" != "1" ]]; then
  LOG_FILE="${DOCMANCER_LIVE_LOG_FILE:-$SCRIPT_DIR/live_cli_integration_$(date +%Y%m%d_%H%M%S).log}"
  mkdir -p "$(dirname "$LOG_FILE")"
  exec > >(tee "$LOG_FILE") 2>&1
fi

VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
CLI_CMD=("$VENV_PYTHON" -m docmancer)
export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
export PATH="$ROOT_DIR/.venv/bin:$PATH"

DOCS_URL="${DOCMANCER_LIVE_DOCS_URL:-https://docs.pytest.org}"
MAX_PAGES="${DOCMANCER_LIVE_MAX_PAGES:-2}"
FETCH_WORKERS="${DOCMANCER_LIVE_FETCH_WORKERS:-8}"
ADD_PROVIDER="${DOCMANCER_LIVE_PROVIDER:-auto}"
ADD_STRATEGY="${DOCMANCER_LIVE_STRATEGY:-}"
RUN_WEB_VARIANTS="${DOCMANCER_RUN_WEB_VARIANTS:-0}"
RUN_BROWSER_VARIANT="${DOCMANCER_RUN_BROWSER_VARIANT:-0}"
RUN_CRAWL4AI_VARIANT="${DOCMANCER_RUN_CRAWL4AI_VARIANT:-0}"
RUN_GITHUB_BLOB="${DOCMANCER_RUN_GITHUB_BLOB:-1}"
GITHUB_BLOB_URL="${DOCMANCER_GITHUB_BLOB_URL:-https://github.com/pytest-dev/pytest/blob/main/README.rst}"
RUN_FETCH_STEP="${DOCMANCER_RUN_FETCH_STEP:-1}"
RUN_LOCAL_CORPUS="${DOCMANCER_RUN_LOCAL_CORPUS:-1}"
RUN_LOCAL_PDF_CORPUS="${DOCMANCER_RUN_LOCAL_PDF_CORPUS:-1}"
BUILD_TEST_CORPUS="${DOCMANCER_BUILD_TEST_CORPUS:-0}"
TEST_CORPUS_SCRIPT="$WORKSPACE_ROOT/scripts/build-test-corpus.py"
TEST_CORPUS_MD_DIR="$WORKSPACE_ROOT/test-corpora/stories-md"
TEST_CORPUS_PDF_DIR="$WORKSPACE_ROOT/test-corpora/stories-pdf"
SKIP_NETWORK="${DOCMANCER_SKIP_NETWORK:-0}"
# Set to 1 to keep the temp dir for inspection; default removes it on every exit.
KEEP_TMP="${DOCMANCER_KEEP_TMP:-0}"
REQUIRE_REFRESH="${DOCMANCER_REQUIRE_REFRESH:-0}"
# Opt-in: exercise the full vector-retrieval stack end-to-end. Off by default
# because it downloads the pinned Qdrant binary (~60 MB) on first run and
# pulls FastEmbed dense + SPLADE models (~500 MB) into the test HOME. The
# default local-corpus path covers the new CLI *surface* (qdrant status,
# help, etc.) without spawning anything. The later live add path may still
# start managed Qdrant because URL ingestion uses vector sync by default.
RUN_VECTOR_STACK="${DOCMANCER_RUN_VECTOR_STACK:-0}"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Missing repo venv at $VENV_PYTHON"
  echo "Create it first, then rerun this script."
  exit 1
fi

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/docmancer-live-cli.XXXXXX")"
TMP_ROOT="$(cd "$TMP_ROOT" && pwd -P)"
TMP_HOME="$TMP_ROOT/home"
PROJECT_DIR="$TMP_ROOT/project"
FETCH_DIR="$TMP_ROOT/fetched-docs"
LOCAL_REGISTRY_DIR="$TMP_ROOT/local-registry"
CONFIG_PATH="$PROJECT_DIR/docmancer.yaml"

cleanup() {
  if [[ -x "$VENV_PYTHON" ]]; then
    "$VENV_PYTHON" -m docmancer qdrant down >/dev/null 2>&1 || true
  fi
  if [[ "$KEEP_TMP" == "1" ]]; then
    echo
    echo "Temporary files kept at: $TMP_ROOT"
    return
  fi
  rm -rf "$TMP_ROOT" || true
}
# Always remove TMP_ROOT on exit unless DOCMANCER_KEEP_TMP=1 (success or failure).
trap 'cleanup' EXIT

mkdir -p "$TMP_HOME" "$PROJECT_DIR" "$FETCH_DIR"
export HOME="$TMP_HOME"
export XDG_CONFIG_HOME="$TMP_HOME/.config"
export XDG_DATA_HOME="$TMP_HOME/.local/share"
export DOCMANCER_HOME="$TMP_HOME/.docmancer"

print_banner() {
  echo
  echo "=== $1 ==="
}

print_info() {
  echo "  [--] $1"
}

print_ok() {
  echo "  [OK] $1"
}

print_warn() {
  echo "  [!!] $1"
}

run() {
  echo
  printf '$'
  printf ' %q' "$@"
  echo
  "$@"
}

run_live_add() {
  local browser_flag="${1:-0}"
  local max_pages="${2:-$MAX_PAGES}"
  local provider="${3:-$ADD_PROVIDER}"
  local strategy="${4:-$ADD_STRATEGY}"
  local recreate_flag="${5:-1}"
  local cmd=("${CLI_CMD[@]}" add "$DOCS_URL" --max-pages "$max_pages" --fetch-workers "$FETCH_WORKERS" --config "$CONFIG_PATH")

  if [[ "$recreate_flag" == "1" ]]; then
    cmd+=(--recreate)
  fi
  if [[ -n "$provider" && "$provider" != "auto" ]]; then
    cmd+=(--provider "$provider")
  fi
  if [[ -n "$strategy" ]]; then
    cmd+=(--strategy "$strategy")
  fi
  if [[ "$browser_flag" == "1" ]]; then
    cmd+=(--browser)
  fi

  run "${cmd[@]}"
}

capture_first_source() {
  "${CLI_CMD[@]}" list --all --config "$CONFIG_PATH" \
    | awk 'NF >= 2 && $0 !~ /^No sources indexed yet\.$/ {print $NF; exit}'
}

create_fake_mcp_registry() {
  local registry_dir="$1"
  "$VENV_PYTHON" - "$registry_dir" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
pack = root / "open-meteo@v1"
pack.mkdir(parents=True, exist_ok=True)

contract = {
    "docmancer_contract_version": "1",
    "package": "open-meteo",
    "version": "v1",
    "source": {
        "kind": "openapi",
        "url": "https://example.invalid/open-meteo-openapi.yml",
        "sha256": "fixture",
        "fetched_at": "2026-04-27T00:00:00Z",
    },
    "auth": {"schemes": []},
    "operations": [
        {
            "id": "forecast",
            "summary": "Current and 7-day weather forecast",
            "description": "Returns weather variables for a given lat/lon. No API key required.",
            "executor": "http",
            "http": {
                "method": "GET",
                "path": "/v1/forecast",
                "base_url": "https://api.open-meteo.com",
                "encoding": "query_only",
            },
            "params": [
                {"name": "latitude", "in": "query", "type": "number", "required": True},
                {"name": "longitude", "in": "query", "type": "number", "required": True},
                {"name": "current_weather", "in": "query", "type": "boolean", "required": False},
            ],
            "inputSchema": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number"},
                    "longitude": {"type": "number"},
                    "current_weather": {"type": "boolean"},
                },
                "required": ["latitude", "longitude"],
                "additionalProperties": False,
            },
            "safety": {"destructive": False, "requires_auth": False, "idempotent": True},
            "examples": [{"args": {"latitude": 40.785091, "longitude": -73.968285, "current_weather": True}}],
        },
    ],
    "schemas": {},
    "curation": {
        "operation_ids": ["forecast"],
        "source": "fixture",
        "generated_at": "2026-04-27T00:00:00Z",
    },
}

tools_curated = {
    "tools": [
        {
            "operation_id": "forecast",
            "description": "Current and 7-day weather forecast for a lat/lon. No API key required.",
            "executor": "http",
            "safety": {"destructive": False, "requires_auth": False, "idempotent": True},
            "inputSchema": contract["operations"][0]["inputSchema"],
        },
    ]
}

tools_full = {"tools": tools_curated["tools"]}

auth_schema = {"schemes": []}
provenance = {"source": "live_cli_integration fixture", "docmancer_version": "local", "sha256": "fixture"}

for name, payload in {
    "contract.json": contract,
    "tools.curated.json": tools_curated,
    "tools.full.json": tools_full,
    "auth.schema.json": auth_schema,
    "provenance.json": provenance,
}.items():
    (pack / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

print(f"Wrote fake MCP registry pack to {pack}")
PY
}

print_banner "docmancer live CLI integration"
echo "Repo root: $ROOT_DIR"
echo "Using venv python: $VENV_PYTHON"
echo "Temporary HOME: $HOME"
echo "Temporary project: $PROJECT_DIR"
echo "Docmancer home: $DOCMANCER_HOME"
echo "Local registry fixture: $LOCAL_REGISTRY_DIR"
echo "Log file: ${LOG_FILE:-disabled (DOCMANCER_LIVE_NO_LOG=1)}"

print_banner "Run configuration"
print_info "MCP walkthrough: emulates docs/api-mcp/open-meteo-walkthrough.md (Steps 0-3)"
print_info "Local crawl URL: $DOCS_URL"
print_info "Local crawl cap: $MAX_PAGES page(s), $FETCH_WORKERS worker(s)"
print_info "Local crawl provider: $ADD_PROVIDER"
print_info "Local crawl strategy: ${ADD_STRATEGY:-<default>}"
print_info "Fetch markdown step: $RUN_FETCH_STEP"
print_info "Local story corpus ingest: $RUN_LOCAL_CORPUS"
print_info "Local PDF corpus ingest: $RUN_LOCAL_PDF_CORPUS"
print_info "Build test corpus if missing: $BUILD_TEST_CORPUS"
print_info "Alternate web strategy: $RUN_WEB_VARIANTS"
print_info "Browser fallback variant: $RUN_BROWSER_VARIANT"
print_info "Crawl4AI variant: $RUN_CRAWL4AI_VARIANT"
print_info "GitHub blob URL test: $RUN_GITHUB_BLOB ($GITHUB_BLOB_URL)"
print_info "Skip all network work: $SKIP_NETWORK"
print_info "Vector retrieval stack (Qdrant + FastEmbed): $RUN_VECTOR_STACK"
print_info "Keep temporary files: $KEEP_TMP"
print_info "Require editable reinstall: $REQUIRE_REFRESH"
if [[ "$SKIP_NETWORK" == "1" ]]; then
  print_info "MCP pack install uses a local registry fixture because DOCMANCER_SKIP_NETWORK=1."
else
  print_info "MCP pack install uses the zero-config resolver: local cache, hosted registry, then Open-Meteo OpenAPI fallback."
fi

cd "$ROOT_DIR"

print_banner "Refreshing local editable install"
if "$VENV_PYTHON" -c "import hatchling.build, editables" >/dev/null 2>&1; then
  if run "$VENV_PYTHON" -m pip install --no-build-isolation -e ".[dev]"; then
    print_ok "Editable install refreshed from the current source tree."
  elif [[ "$REQUIRE_REFRESH" == "1" ]]; then
    print_warn "Editable reinstall failed and DOCMANCER_REQUIRE_REFRESH=1 was set."
    exit 1
  else
    print_warn "Editable reinstall failed. Continuing with the repo source tree via PYTHONPATH."
  fi
elif [[ "$REQUIRE_REFRESH" == "1" ]]; then
  print_warn "Editable reinstall required, but hatchling.build and/or editables is unavailable in $VENV_PYTHON."
  print_warn "Install the editable build dependencies into the repo venv or recreate the venv, then rerun."
  exit 1
else
  print_warn "Skipping editable reinstall because hatchling.build and/or editables is unavailable in the repo venv."
  print_info "Continuing with the repo source tree via: ${CLI_CMD[*]}"
fi
run "$VENV_PYTHON" -c "import docmancer, sys; print('python=', sys.executable); print('docmancer=', docmancer.__file__)"

print_banner "CLI help surface"
print_info "Checking top-level help plus local indexing, MCP, pack install, install, and maintenance commands."
run "${CLI_CMD[@]}" --help
for command in setup add update query list inspect remove doctor init install fetch ingest mcp install-pack uninstall qdrant; do
  run "${CLI_CMD[@]}" "$command" --help
done
for command in up down status upgrade logs; do
  run "${CLI_CMD[@]}" qdrant "$command" --help
done
for command in serve doctor list enable disable remove; do
  run "${CLI_CMD[@]}" mcp "$command" --help
done

print_banner "Initialize isolated config"
print_info "Creating a project config in the temporary project directory."
run "${CLI_CMD[@]}" init --dir "$PROJECT_DIR"
run cat "$CONFIG_PATH"

print_banner "Setup in isolated HOME (non-interactive)"
print_info "Installing the default local config and agent files into the temporary HOME only."
run "${CLI_CMD[@]}" setup --all --config "$CONFIG_PATH"

print_banner "Install targets in isolated HOME"
print_info "Exercising every supported install target without touching the real HOME."
run "${CLI_CMD[@]}" install claude-code --config "$CONFIG_PATH"
(
  cd "$PROJECT_DIR"
  run "$VENV_PYTHON" -m docmancer install claude-code --project --config "$CONFIG_PATH"
  run "$VENV_PYTHON" -m docmancer install cline --project --config "$CONFIG_PATH"
)
for agent in claude-desktop cline cursor codex codex-app codex-desktop gemini github-copilot opencode; do
  run "${CLI_CMD[@]}" install "$agent" --config "$CONFIG_PATH"
done

print_banner "Open-Meteo walkthrough Step 0: prerequisites"
print_info "Agent install (above) already registered docmancer mcp docs-serve into Claude Code/Cursor/Claude Desktop MCP configs. Verifying entries exist."
run "$VENV_PYTHON" - <<'PY'
import json, os, pathlib, sys

home = pathlib.Path(os.environ["HOME"])
checks = [
    home / ".claude" / "mcp_servers.json",
    home / ".cursor" / "mcp.json",
    home / "Library/Application Support/Claude/claude_desktop_config.json",
]
found = 0
for path in checks:
    if not path.exists():
        continue
    data = json.loads(path.read_text())
    servers = data.get("mcpServers", {})
    if "docmancer" in servers:
        entry = servers["docmancer"]
        print(f"[ok] {path}: docmancer -> {entry.get('command')} {' '.join(entry.get('args', []))}")
        found += 1
    else:
        print(f"[!!] {path} present but has no docmancer entry: {list(servers)}")
if found == 0:
    print("[!!] no agent MCP config registered docmancer; install step did not wire anything")
    sys.exit(1)
print(f"docmancer MCP server registered in {found} agent config(s).")
PY

print_banner "Open-Meteo walkthrough Step 1: install the Open-Meteo pack"
if [[ "$SKIP_NETWORK" == "1" ]]; then
  print_info "Building a fake Open-Meteo registry pack pinned at v1."
  create_fake_mcp_registry "$LOCAL_REGISTRY_DIR"
  export DOCMANCER_REGISTRY_DIR="$LOCAL_REGISTRY_DIR"
else
  print_info "Installing Open-Meteo through the zero-config resolver. No registry env vars are set for users."
  unset DOCMANCER_REGISTRY_DIR
  unset DOCMANCER_REGISTRY_API_URL
fi
run "${CLI_CMD[@]}" mcp list
run "${CLI_CMD[@]}" install-pack open-meteo@v1
run "${CLI_CMD[@]}" mcp list

print_banner "Open-Meteo walkthrough Step 2: doctor (no credentials required)"
print_info "Open-Meteo is keyless. mcp doctor should pass with no FAIL and skip credential resolution entirely."
run "${CLI_CMD[@]}" mcp doctor

print_banner "Open-Meteo walkthrough Step 3: forecast call against a mocked transport"
print_info "The dispatcher exposes 2 meta-tools regardless of pack count. Step 3: search → dispatch GET /v1/forecast against a mocked httpx transport. Verifies no Authorization header is sent (no auth required) and no Idempotency-Key (GET is idempotent)."
run "$VENV_PYTHON" - <<'PY'
import httpx
from docmancer.mcp.dispatcher import Dispatcher
import docmancer.mcp.dispatcher as disp_mod
from docmancer.mcp.executors.http import HttpExecutor
from docmancer.mcp.manifest import Manifest

captured = []
def handler(req):
    captured.append({
        "method": req.method,
        "url": str(req.url),
        "headers": dict(req.headers),
        "content": req.content.decode() if req.content else "",
    })
    return httpx.Response(
        200,
        json={
            "latitude": 40.785,
            "longitude": -73.968,
            "current_weather": {
                "time": "2026-04-28T14:00",
                "temperature": 15.4,
                "windspeed": 7.3,
                "weathercode": 3,
                "is_day": 1,
            },
        },
    )

client = httpx.Client(transport=httpx.MockTransport(handler))
disp_mod.get_executor = lambda kind: HttpExecutor(client=client) if kind == "http" else disp_mod.get_executor(kind)

dispatcher = Dispatcher(Manifest.load())
tools = dispatcher.list_tools()
assert [t["name"] for t in tools] == ["docmancer_search_tools", "docmancer_call_tool"], tools
print(f"Step 3a: tools/list returned {len(tools)} meta-tool(s) (Tool Search pattern, D10).")

matches = dispatcher.search_tools(query="current temperature forecast latitude longitude", package="open-meteo", limit=20)["matches"]
match = next((m for m in matches if m["name"] == "open_meteo__v1__forecast"), None)
assert match, matches
print(f"Step 3b: search selected match = {match['name']} (slug format D15 verified).")

result = dispatcher.call_tool(
    match["name"],
    {"latitude": 40.785091, "longitude": -73.968285, "current_weather": True},
)
assert result.ok, result.body
req = captured[-1]
assert req["method"] == "GET", req
assert "latitude=40.785091" in req["url"], req["url"]
assert "longitude=-73.968285" in req["url"], req["url"]
assert "current_weather=true" in req["url"].lower(), req["url"]
assert "authorization" not in (k.lower() for k in req["headers"]), req["headers"]
assert "idempotency-key" not in (k.lower() for k in req["headers"]), req["headers"]
print(f"Step 3c: GET {req['url']} sent with no Authorization header (keyless), no Idempotency-Key (idempotent op).")
temp = result.body.get("current_weather", {}).get("temperature")
assert isinstance(temp, (int, float)), result.body
print(f"Step 3d: response.current_weather.temperature = {temp}°C (Central Park, NYC, mocked transport).")

# Schema validation in dispatcher (2.8.5): Tool Search hides per-tool schemas from MCP, dispatcher must validate.
invalid = dispatcher.call_tool(
    "open_meteo__v1__forecast",
    {"latitude": "not-a-number", "longitude": -73.96},
)
assert not invalid.ok and invalid.error_code == "invalid_args", invalid.body
print("Schema validation: invalid_args rejected (2.8.5).")
PY

print_banner "MCP enable / disable toggles + uninstall + mcp remove"
print_info "Verifying mcp enable / disable still flip per-package state without reinstalling, then cleanly uninstall."
run "${CLI_CMD[@]}" mcp disable open-meteo --version v1
run "${CLI_CMD[@]}" mcp list
run "${CLI_CMD[@]}" mcp enable open-meteo --version v1
run "${CLI_CMD[@]}" mcp list
run "${CLI_CMD[@]}" uninstall open-meteo@v1
run "${CLI_CMD[@]}" mcp list

print_info "Reinstalling open-meteo so we can exercise the new docmancer mcp remove subcommand."
run "${CLI_CMD[@]}" install-pack open-meteo@v1
run "${CLI_CMD[@]}" mcp list
run "${CLI_CMD[@]}" mcp remove open-meteo@v1
run "${CLI_CMD[@]}" mcp list

print_banner "Doctor and inspect before docs-RAG add"
print_info "The local index should still be empty before any live crawl."
run "${CLI_CMD[@]}" doctor --config "$CONFIG_PATH"
run "${CLI_CMD[@]}" list --config "$CONFIG_PATH"

if [[ "$RUN_LOCAL_CORPUS" == "1" ]]; then
  print_banner "Local story corpus ingest"
  if [[ "$BUILD_TEST_CORPUS" == "1" || ! -d "$TEST_CORPUS_MD_DIR" || -z "$(find "$TEST_CORPUS_MD_DIR" -maxdepth 1 -name '*.md' -print -quit 2>/dev/null)" ]]; then
    if [[ ! -f "$TEST_CORPUS_SCRIPT" ]]; then
      print_warn "Missing corpus builder at $TEST_CORPUS_SCRIPT"
      exit 1
    fi
    print_info "Building local story corpus from Project Gutenberg sources."
    run python3 "$TEST_CORPUS_SCRIPT"
  fi

  if [[ ! -d "$TEST_CORPUS_MD_DIR" ]]; then
    print_warn "Missing Markdown story corpus at $TEST_CORPUS_MD_DIR"
    exit 1
  fi
  print_info "Indexing Markdown story corpus from $TEST_CORPUS_MD_DIR via docmancer ingest --no-vectors"
  print_info "FTS5-only here so the default fast path does not download FastEmbed models. Set DOCMANCER_RUN_VECTOR_STACK=1 to exercise the full hybrid path."
  run "${CLI_CMD[@]}" ingest "$TEST_CORPUS_MD_DIR" --recreate --no-vectors --config "$CONFIG_PATH"
  run "${CLI_CMD[@]}" inspect --config "$CONFIG_PATH"
  run "${CLI_CMD[@]}" list --all --config "$CONFIG_PATH"
  run "${CLI_CMD[@]}" query "curiouser" --limit 3 --mode lexical --explain --config "$CONFIG_PATH"
fi

if [[ "$RUN_LOCAL_PDF_CORPUS" == "1" ]]; then
  print_banner "Local PDF story corpus ingest"
  if [[ ! -d "$TEST_CORPUS_PDF_DIR" || -z "$(find "$TEST_CORPUS_PDF_DIR" -maxdepth 1 -name '*.pdf' -print -quit 2>/dev/null)" ]]; then
    if [[ "$BUILD_TEST_CORPUS" == "1" && -f "$TEST_CORPUS_SCRIPT" ]]; then
      print_info "Building local PDF story corpus because no PDFs were found."
      run python3 "$TEST_CORPUS_SCRIPT"
    else
      print_warn "Missing PDF story corpus at $TEST_CORPUS_PDF_DIR. Run: python3 $TEST_CORPUS_SCRIPT"
      exit 1
    fi
  fi
  print_info "Indexing PDF story corpus from $TEST_CORPUS_PDF_DIR via docmancer ingest --no-vectors"
  run "${CLI_CMD[@]}" ingest "$TEST_CORPUS_PDF_DIR" --recreate --no-vectors --config "$CONFIG_PATH"
  run "${CLI_CMD[@]}" inspect --config "$CONFIG_PATH"
  run "${CLI_CMD[@]}" list --all --config "$CONFIG_PATH"
  run "${CLI_CMD[@]}" query "Sherlock Holmes hound baskervilles" --limit 3 --config "$CONFIG_PATH"
fi

print_banner "Qdrant lifecycle command surface"
print_info "qdrant status: must report not-running on a fresh isolated HOME."
run "${CLI_CMD[@]}" qdrant status
run "${CLI_CMD[@]}" qdrant status --json
print_info "qdrant up --docker: emits a compose snippet, does not spawn the managed binary."
run "${CLI_CMD[@]}" qdrant up --docker
print_info "qdrant down: must be a clean no-op when nothing is running."
run "${CLI_CMD[@]}" qdrant down

if [[ "$RUN_VECTOR_STACK" == "1" ]]; then
  print_banner "Vector stack end-to-end (Qdrant + FastEmbed + hybrid retrieval)"
  if [[ "$SKIP_NETWORK" == "1" ]]; then
    print_warn "DOCMANCER_RUN_VECTOR_STACK=1 and DOCMANCER_SKIP_NETWORK=1 are incompatible (need to download the Qdrant binary and FastEmbed models). Skipping."
  elif [[ ! -d "$TEST_CORPUS_MD_DIR" ]]; then
    print_warn "Missing Markdown story corpus at $TEST_CORPUS_MD_DIR; vector stack run requires it."
  else
    print_info "Starting managed Qdrant in the isolated DOCMANCER_HOME ($DOCMANCER_HOME/qdrant)."
    run "${CLI_CMD[@]}" qdrant up
    run "${CLI_CMD[@]}" qdrant status
    print_info "Re-ingesting the story corpus with vectors enabled. First run pulls FastEmbed models into $HOME/.docmancer/models."
    run "${CLI_CMD[@]}" ingest "$TEST_CORPUS_MD_DIR" --recreate --config "$CONFIG_PATH"
    run "${CLI_CMD[@]}" inspect --config "$CONFIG_PATH"
    print_info "Hybrid retrieval should surface contributions from at least two signals."
    run "${CLI_CMD[@]}" query "curiouser" --mode hybrid --explain --limit 3 --config "$CONFIG_PATH"
    run "${CLI_CMD[@]}" query "curiouser" --mode dense --explain --limit 3 --config "$CONFIG_PATH"
    print_info "Stopping the managed Qdrant so we leave no daemon behind."
    run "${CLI_CMD[@]}" qdrant down
    run "${CLI_CMD[@]}" qdrant status
  fi
else
  print_info "Skipping the explicit vector-stack query round-trip (DOCMANCER_RUN_VECTOR_STACK=0). A later live URL add may still start managed Qdrant for vector sync."
fi

if [[ "$SKIP_NETWORK" == "1" ]]; then
  print_banner "Network steps skipped"
  print_info "DOCMANCER_SKIP_NETWORK=1, stopping before fetch and live add."
  exit 0
fi

if [[ "$RUN_FETCH_STEP" == "1" ]]; then
  print_banner "Fetch live pytest docs to markdown files"
  print_info "Fetching raw markdown files from $DOCS_URL without indexing them."
  if run "${CLI_CMD[@]}" fetch "$DOCS_URL" --output "$FETCH_DIR"; then
    run find "$FETCH_DIR" -maxdepth 1 -type f
  else
    print_warn "Fetch step failed or is unsupported for this docs site. Continuing with local add."
  fi
fi

print_banner "Add live pytest docs URL with bounded local crawl"
print_info "Indexing a small live pytest docs crawl into the isolated SQLite database."
run_live_add 0 "$MAX_PAGES"
run "${CLI_CMD[@]}" inspect --config "$CONFIG_PATH"
run "${CLI_CMD[@]}" doctor --config "$CONFIG_PATH"
run "${CLI_CMD[@]}" list --config "$CONFIG_PATH"
run "${CLI_CMD[@]}" list --all --config "$CONFIG_PATH"
run "${CLI_CMD[@]}" query "assert statements" --limit 5 --config "$CONFIG_PATH" || true
run "${CLI_CMD[@]}" query "assert statements" --limit 1 --expand page --config "$CONFIG_PATH" || true

print_banner "Update all indexed sources"
print_info "Refreshing every currently indexed source in the isolated database."
run "${CLI_CMD[@]}" update --max-pages "$MAX_PAGES" --config "$CONFIG_PATH"
run "${CLI_CMD[@]}" inspect --config "$CONFIG_PATH"

if [[ "$RUN_WEB_VARIANTS" == "1" ]]; then
  print_banner "Add live pytest docs with alternate explicit web strategy"
  print_info "Running the generic web fetcher with nav-crawl to compare behavior."
  run_live_add 0 20 web nav-crawl
  run "${CLI_CMD[@]}" inspect --config "$CONFIG_PATH"
  run "${CLI_CMD[@]}" doctor --config "$CONFIG_PATH"
fi

if [[ "$RUN_BROWSER_VARIANT" == "1" ]]; then
  print_banner "Add live pytest docs with browser fallback"
  print_info "Running the browser-backed fetch path. This requires Playwright/browser dependencies in the venv."
  run_live_add 1 20 web nav-crawl
  run "${CLI_CMD[@]}" inspect --config "$CONFIG_PATH"
  run "${CLI_CMD[@]}" doctor --config "$CONFIG_PATH"
fi

if [[ "$RUN_CRAWL4AI_VARIANT" == "1" ]]; then
  print_banner "Add live pytest docs with Crawl4AI provider"
  print_info "Running the Crawl4AI-backed fetch path. Requires: pip install docmancer[crawl4ai] && crawl4ai-setup"
  run_live_add 0 20 crawl4ai
  run "${CLI_CMD[@]}" inspect --config "$CONFIG_PATH"
  run "${CLI_CMD[@]}" doctor --config "$CONFIG_PATH"
fi

if [[ "$RUN_GITHUB_BLOB" == "1" ]]; then
  print_banner "Add a single GitHub blob URL (pytest README)"
  print_info "Fetching a single markdown file via a GitHub /blob/ URL: $GITHUB_BLOB_URL"
  run "${CLI_CMD[@]}" add "$GITHUB_BLOB_URL" --recreate --config "$CONFIG_PATH"
  run "${CLI_CMD[@]}" inspect --config "$CONFIG_PATH"
  run "${CLI_CMD[@]}" list --all --config "$CONFIG_PATH"
  # Query with a pytest-related term; tolerate no-results (exit 1) gracefully.
  run "${CLI_CMD[@]}" query "pytest install" --limit 3 --config "$CONFIG_PATH" || true
fi

REMOTE_SOURCE="$(capture_first_source)"
if [[ -n "$REMOTE_SOURCE" ]]; then
  print_banner "Remove a single live source or docset"
  print_info "Removing the first indexed source reported by docmancer list --all: $REMOTE_SOURCE"
  run "${CLI_CMD[@]}" remove "$REMOTE_SOURCE" --config "$CONFIG_PATH"
  run "${CLI_CMD[@]}" list --all --config "$CONFIG_PATH"
fi

print_banner "Library API smoke test"
print_info "Exercising the programmatic DocmancerClient, format_context, and AsyncDocmancerAgent APIs."
run "$VENV_PYTHON" -c "
import sys, pathlib, tempfile

# Verify all public exports are importable.
from docmancer import (
    DocmancerAgent, AsyncDocmancerAgent, DocmancerClient,
    DocmancerConfig, Document, RetrievedChunk, Chunk,
    format_context, build_rag_prompt,
)
print('All public exports imported OK')

# DocmancerClient: ingest a local file and query.
tmp = pathlib.Path(tempfile.mkdtemp())
db_path = str(tmp / 'lib_test.db')
md_file = tmp / 'sample.md'
md_file.write_text('# Auth\n\nUse OAuth tokens.\n\n# API\n\nCall POST /api/v1/login.\n')

client = DocmancerClient(db_path=db_path)
sections = client.add(str(md_file))
print(f'DocmancerClient.add indexed {sections} section(s)')

ctx_md = client.get_context('OAuth tokens', style='markdown')
print(f'Markdown context ({len(ctx_md)} chars): {ctx_md[:80]}...')

ctx_xml = client.get_context('login endpoint', style='xml')
print(f'XML context ({len(ctx_xml)} chars): {ctx_xml[:80]}...')

ctx_plain = client.get_context('oauth', style='plain')
print(f'Plain context ({len(ctx_plain)} chars): {ctx_plain[:80]}...')

# format_context standalone.
chunks = client.get_chunks('auth')
formatted = format_context(chunks, style='xml', include_sources=True)
assert '<doc' in formatted, 'format_context XML output missing <doc> tag'
print(f'format_context OK ({len(formatted)} chars)')

# build_rag_prompt.
prompt = build_rag_prompt(chunks, 'How do I log in?', instruction='Be concise.')
assert 'Question: How do I log in?' in prompt
print(f'build_rag_prompt OK ({len(prompt)} chars)')

# AsyncDocmancerAgent round-trip.
import asyncio
from docmancer.core.config import DocmancerConfig, IndexConfig
async_db = str(tmp / 'async_test.db')
cfg = DocmancerConfig(index=IndexConfig(db_path=async_db))
agent = AsyncDocmancerAgent(config=cfg)
async def _run():
    n = await agent.ingest_documents([
        Document(source='test://a', content='# Hello\n\nWorld.', metadata={}),
    ])
    r = await agent.query('hello')
    ctx = await agent.query_context('hello', style='xml')
    return n, len(r), len(ctx)
n, rcount, clen = asyncio.run(_run())
print(f'AsyncDocmancerAgent: ingested={n}, results={rcount}, context_len={clen}')

print('Library API smoke test passed.')
"
print_ok "Programmatic API exercised successfully."

print_banner "Remove all data"
print_info "Clearing the isolated index to verify removal behavior and final doctor output."
run "${CLI_CMD[@]}" remove --all --config "$CONFIG_PATH"
run "${CLI_CMD[@]}" list --config "$CONFIG_PATH"
print_info "Stopping any managed Qdrant started by vector sync before the final doctor check."
run "${CLI_CMD[@]}" qdrant down
run "${CLI_CMD[@]}" doctor --config "$CONFIG_PATH"

print_banner "Live CLI integration finished"
print_ok "Completed local CLI integration script."
