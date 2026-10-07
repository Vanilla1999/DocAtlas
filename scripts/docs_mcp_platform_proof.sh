#!/usr/bin/env bash
# Finite installed-wheel platform proof. No live config, providers or publishing.
# Usage: bash scripts/docs_mcp_platform_proof.sh ABS_WHEEL SOURCE_SHA ABS_ARTIFACT_DIR
set -euo pipefail
umask 077
[[ $# -eq 3 && $1 = /* && $3 = /* ]] || {
  echo "Usage: $0 ABS_WHEEL SOURCE_SHA ABS_ARTIFACT_DIR" >&2
  exit 2
}
wheel=$1
source_sha=$2
mkdir -p "$3"
artifacts=$(cd "$3" && pwd -P)
trap 'code=$?; printf "%s\n" "$code" > "$artifacts/proof-exit-status.txt"' EXIT
exec > >(tee "$artifacts/proof.log") 2>&1
checkout=$(cd "$(dirname "$0")/.." && pwd -P)
printf '%s\n' "$source_sha" > "$artifacts/source-sha.txt"
uname -a > "$artifacts/uname.txt"
uname -m > "$artifacts/architecture.txt"
[[ $(git -C "$checkout" rev-parse HEAD) = "$source_sha" ]]
[[ -f $wheel ]]
wheel=$(cd "$(dirname "$wheel")" && printf '%s/%s' "$(pwd -P)" "$(basename "$wheel")")
shasum -a 256 "$wheel" > "$artifacts/wheel-sha256.txt"
uv_binary=$(command -v uv)
[[ $uv_binary = /* && -x $uv_binary ]]

# Resolve HOME before mktemp: macOS symlink aliases must not introduce unsafe
# fixture ancestors. Never use /tmp, the checkout, or another user's namespace.
physical_home=$(cd "$HOME" && pwd -P)
namespace=$(mktemp -d "$physical_home/.docatlas-platform-proof.XXXXXXXX")
namespace=$(cd "$namespace" && pwd -P)
chmod 700 "$namespace"
printf '%s\n' "$namespace" > "$artifacts/private-namespace.txt"
mkdir -p "$namespace"/{home,tools,bin,cache,python,config,data,state,runtime,tmp,cwd,infra}
# Expose only host uv as infrastructure, not the build venv/host tool directory.
ln -s "$uv_binary" "$namespace/infra/uv"
clean_env=(
  "HOME=$namespace/home"
  "PATH=$namespace/bin:$namespace/infra:/usr/bin:/bin:/usr/sbin:/sbin"
  "TMPDIR=$namespace/tmp" "LANG=C.UTF-8"
  "UV_TOOL_DIR=$namespace/tools" "UV_TOOL_BIN_DIR=$namespace/bin"
  "UV_CACHE_DIR=$namespace/cache" "UV_PYTHON_INSTALL_DIR=$namespace/python"
  "UV_NO_CONFIG=1" "UV_PYTHON_PREFERENCE=only-managed"
  "UV_PYTHON_DOWNLOADS=automatic"
  "XDG_CONFIG_HOME=$namespace/config" "XDG_DATA_HOME=$namespace/data"
  "XDG_CACHE_HOME=$namespace/cache" "XDG_STATE_HOME=$namespace/state"
  "XDG_RUNTIME_DIR=$namespace/runtime"
  "PYTHONNOUSERSITE=1" "PYTHONDONTWRITEBYTECODE=1" "PYTHONUNBUFFERED=1"
  "DOCATLAS_INSTALL_PYTHON=3.13" "DOCATLAS_INSTALL_SOURCE=$wheel"
)
# Explicit transport-only allowlist; no provider credentials, live configuration,
# PYTHONPATH, VIRTUAL_ENV, uv overrides or Actions tokens cross the boundary.
for key in HTTPS_PROXY HTTP_PROXY ALL_PROXY NO_PROXY https_proxy http_proxy all_proxy no_proxy SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE CURL_CA_BUNDLE; do
  if [[ -n ${!key:-} ]]; then clean_env+=("$key=${!key}"); fi
done

env -i "${clean_env[@]}" /bin/bash -s -- "$wheel" "$checkout" "$namespace" "$artifacts" <<'PROOF'
set -euo pipefail
umask 077
wheel=$1 checkout=$2 namespace=$3 artifacts=$4
cd "$namespace/cwd"
uv --version | tee "$artifacts/uv-version.txt"
[[ -z $(ls -A "$UV_PYTHON_INSTALL_DIR") && -z $(ls -A "$UV_CACHE_DIR") && -z $(ls -A "$UV_TOOL_DIR") ]]
# This must DOWNLOAD into an empty directory, never reuse setup-python or a
# preinstalled runtime. Managed-only discovery also applies to the installer.
uv python install 3.13
managed_python=$(uv python find --managed-python 3.13)
[[ $managed_python = "$UV_PYTHON_INSTALL_DIR/"* ]]
"$managed_python" -I - "$checkout" "$wheel" "$artifacts" <<'PY'
import ast
import email
import hashlib
from pathlib import Path
import sys
import tomllib
import zipfile

checkout, wheel, artifacts = map(Path, sys.argv[1:])
project = tomllib.loads((checkout / "pyproject.toml").read_text())
# Read source metadata without importing any checkout modules or dependencies.
version = project["project"].get("version")
if version is None:
    tree = ast.parse((checkout / project["tool"]["hatch"]["version"]["path"]).read_text())
    version = next(ast.literal_eval(node.value) for node in tree.body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets))
with zipfile.ZipFile(wheel) as archive:
    metadata_files = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
    assert len(metadata_files) == 1, metadata_files
    metadata = email.message_from_bytes(archive.read(metadata_files[0]))
assert metadata["Name"] == project["project"]["name"] == "doc-atlas"
assert metadata["Version"] == version, (metadata["Version"], version)
(artifacts / "expected-version.txt").write_text(version + "\n")
print("Wheel SHA256:", hashlib.sha256(wheel.read_bytes()).hexdigest())
print("Fresh managed Python:", sys.version, sys.executable)
(artifacts / "managed-python.txt").write_text(sys.version + "\n" + sys.executable + "\n")
PY
export DOCATLAS_EXPECT_VERSION
DOCATLAS_EXPECT_VERSION=$(cat "$artifacts/expected-version.txt")
# Actual reviewed installer: --no-build is enforced inside it. No registration,
# seed dependencies, copied cache, or source .pth. Only this absolute wheel.
sh "$checkout/scripts/install.sh" none
tool_python="$UV_TOOL_DIR/doc-atlas/bin/python"
[[ -x $tool_python && $(command -v doc-atlas) = "$UV_TOOL_BIN_DIR/doc-atlas" ]]
"$tool_python" -I - "$checkout" "$UV_TOOL_DIR" "$UV_PYTHON_INSTALL_DIR" "$artifacts" <<'PY'
import docmancer
from pathlib import Path
import sys

checkout, tools, managed, artifacts = map(lambda p: Path(p).resolve(), sys.argv[1:])
module = Path(docmancer.__file__).resolve()
prefix = Path(sys.prefix).resolve()
assert prefix.is_relative_to(tools), prefix
assert module.is_relative_to(prefix) and "site-packages" in module.parts, module
assert not module.is_relative_to(checkout), module
assert Path(sys.base_prefix).resolve().is_relative_to(managed), sys.base_prefix
assert sys.version_info[:2] == (3, 13), sys.version
assert all(not Path(p).resolve().is_relative_to(checkout) for p in sys.path), sys.path
for pth in prefix.glob("lib/python*/site-packages/*.pth"):
    assert str(checkout) not in pth.read_text(), pth
(artifacts / "installed-runtime.txt").write_text(
    f"python={sys.executable}\nversion={sys.version}\nbase_prefix={sys.base_prefix}\nmodule={module}\n")
print("Verified installed runtime:", sys.executable, sys.version, module)
PY
# One full existing smoke: cold prepare/retrieve, restart/repeat/CAS, explicit
# versions/scopes and >32KiB unique evidence, BOTH structured/text transports.
# -I excludes the source script directory and user site, without PYTHONPATH.
"$tool_python" -I "$checkout/scripts/docs_mcp_stdio_smoke.py"
PROOF
