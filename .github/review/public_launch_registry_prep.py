from __future__ import annotations

import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.3.2"
SERVER_NAME = "io.github.Vanilla1999/docatlas"


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match for {old!r}, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def prepare_readme_and_version() -> None:
    replace_once(
        "README.md",
        "<!-- mcp-name: io.github.vanilla1999/docatlas -->",
        f"<!-- mcp-name: {SERVER_NAME} -->",
    )
    replace_once(
        "docmancer/_version.py",
        '__version__ = "1.3.1"',
        f'__version__ = "{VERSION}"',
    )
    replace_once(
        "CHANGELOG.md",
        "## [Unreleased]\n\n### Changed\n",
        textwrap.dedent(
            f"""\
            ## [Unreleased]

            ## [{VERSION}] - 2026-09-08

            ### Added

            - Added Official MCP Registry metadata for the local Docs MCP server (`{SERVER_NAME}`) and a GitHub-OIDC publication step that runs only after the exact public PyPI package passes Linux, macOS, and Windows smoke.
            - Added the PyPI ownership marker required by the Official MCP Registry while keeping it hidden from the rendered README.

            ### Changed

            - Reworked the README first screen around the user problem: small, source-attributed project and version-aware dependency context for coding agents, with a one-line install and a compact architecture summary.
            """
        ),
    )


def write_server_json() -> None:
    payload = {
        "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
        "name": SERVER_NAME,
        "title": "DocAtlas",
        "description": "Local-first, version-aware documentation context for coding agents, with bounded source-attributed project and dependency evidence.",
        "websiteUrl": "https://github.com/Vanilla1999/DocAtlas",
        "repository": {
            "url": "https://github.com/Vanilla1999/DocAtlas",
            "source": "github",
        },
        "version": VERSION,
        "packages": [
            {
                "registryType": "pypi",
                "registryBaseUrl": "https://pypi.org",
                "identifier": "doc-atlas",
                "version": VERSION,
                "runtimeHint": "uvx",
                "transport": {"type": "stdio"},
                "packageArguments": [
                    {"type": "positional", "value": "mcp"},
                    {"type": "positional", "value": "docs-serve"},
                ],
            }
        ],
    }
    (ROOT / "server.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def update_publish_workflow() -> None:
    path = ROOT / ".github/workflows/publish.yml"
    text = path.read_text(encoding="utf-8")
    if "for example v1.3.1" not in text:
        raise SystemExit("publish workflow release example not found")
    text = text.replace("for example v1.3.1", "for example v1.3.2", 1)
    if "\n  mcp-registry:\n" in text:
        raise SystemExit("publish workflow already contains mcp-registry job")

    job = textwrap.dedent(
        """

          mcp-registry:
            name: publish-official-mcp-registry
            if: github.event_name == 'workflow_dispatch'
            needs: [public-platform-smoke]
            runs-on: ubuntu-latest
            timeout-minutes: 10
            permissions:
              contents: read
              id-token: write
            steps:
              - uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5
                with:
                  ref: refs/tags/${{ inputs.tag }}
                  persist-credentials: false
              - name: Verify exact MCP Registry metadata
                env:
                  RELEASE_TAG: ${{ inputs.tag }}
                run: |
                  python - <<'PYREG'
                  import json
                  import os
                  from pathlib import Path

                  expected_version = os.environ["RELEASE_TAG"].removeprefix("v")
                  payload = json.loads(Path("server.json").read_text(encoding="utf-8"))
                  expected_name = "io.github.Vanilla1999/docatlas"
                  if payload.get("name") != expected_name:
                      raise SystemExit(f"server name mismatch: {payload.get('name')!r}")
                  if payload.get("version") != expected_version:
                      raise SystemExit(
                          f"server version mismatch: expected={expected_version!r} actual={payload.get('version')!r}"
                      )
                  packages = payload.get("packages") or []
                  if len(packages) != 1:
                      raise SystemExit(f"expected exactly one Registry package, got {len(packages)}")
                  package = packages[0]
                  if package.get("identifier") != "doc-atlas" or package.get("version") != expected_version:
                      raise SystemExit("PyPI package identity/version does not match release")
                  marker = f"<!-- mcp-name: {expected_name} -->"
                  if marker not in Path("README.md").read_text(encoding="utf-8"):
                      raise SystemExit("PyPI README ownership marker is missing")
                  print("MCP Registry release metadata: PASS")
                  PYREG
              - name: Install pinned MCP Registry publisher
                run: |
                  curl -fL \
                    https://github.com/modelcontextprotocol/registry/releases/download/v1.7.9/mcp-publisher_linux_amd64.tar.gz \
                    -o /tmp/mcp-publisher.tar.gz
                  echo 'ab128162b0616090b47cf245afe0a23f3ef08936fdce19074f5ba0a4469281ac  /tmp/mcp-publisher.tar.gz' | sha256sum -c -
                  tar -xzf /tmp/mcp-publisher.tar.gz mcp-publisher
                  ./mcp-publisher --help
              - name: Authenticate to Official MCP Registry
                run: ./mcp-publisher login github-oidc
              - name: Publish to Official MCP Registry
                run: ./mcp-publisher publish server.json
              - name: Verify exact Registry entry
                env:
                  RELEASE_TAG: ${{ inputs.tag }}
                run: |
                  python - <<'PYREG'
                  import json
                  import os
                  import urllib.parse
                  import urllib.request

                  name = "io.github.Vanilla1999/docatlas"
                  version = os.environ["RELEASE_TAG"].removeprefix("v")
                  query = urllib.parse.urlencode({"search": name})
                  url = f"https://registry.modelcontextprotocol.io/v0.1/servers?{query}"
                  request = urllib.request.Request(url, headers={"User-Agent": "DocAtlas-release-verifier/1"})
                  with urllib.request.urlopen(request, timeout=30) as response:
                      payload = json.load(response)

                  def exact(value):
                      if isinstance(value, dict):
                          if value.get("name") == name and value.get("version") == version:
                              return True
                          return any(exact(child) for child in value.values())
                      if isinstance(value, list):
                          return any(exact(child) for child in value)
                      return False

                  if not exact(payload):
                      raise SystemExit(f"published Registry entry not found for {name} {version}")
                  print(f"Official MCP Registry verification: PASS ({name} {version})")
                  PYREG
        """
    )
    path.write_text(text.rstrip() + job + "\n", encoding="utf-8")


def update_release_truth() -> None:
    path = ROOT / "docs/release-identity.md"
    old = path.read_text(encoding="utf-8")
    marker = "## Current `v1.3.1` publication blocker\n"
    if marker not in old:
        raise SystemExit("release identity historical marker not found")
    _, historical = old.split(marker, 1)
    old_retry = textwrap.dedent(
        """\
        ### Safe retry boundary

        After the existing-project publisher is visibly registered with the exact tuple above, retry only the failed jobs of canonical run `32587903026`. Before another retry, require that:

        - public `doc-atlas==1.3.1` is still absent;
        - `v1.3.1` remains an annotated tag targeting `cfa9ab5c365a28d1a4af63afe9f1d53b19532d89`;
        - the original run's gated wheel and sdist artifacts remain available;
        - no token fallback is introduced.

        Do not move or recreate the tag. Do not start a replacement workflow from a newer `main` commit and present its provenance as the tagged source. If the public version appears before the retry, switch to verify-only handling and never overwrite it.
        """
    )
    new_retry = textwrap.dedent(
        """\
        ### Superseded retry boundary

        The two `v1.3.1` failures remain immutable audit evidence. They are no longer the active publication path: the launch and Registry ownership metadata were added after that tag, so the next public candidate is `1.3.2`. Do not move or recreate `v1.3.1`, and do not present a newer tree as that tag.

        After the existing-project PyPI publisher is visibly corrected, create and approve a reviewed `v1.3.2` release request from the exact merged launch tree. No long-lived token fallback is permitted.
        """
    )
    if old_retry not in historical:
        raise SystemExit("historical v1.3.1 retry block not found")
    historical = historical.replace(old_retry, new_retry, 1)
    historical = historical.replace(
        "For clarity, no public `doc-atlas==1.3.1` release is claimed at this pre-public stage.",
        "For clarity, the failed `1.3.1` attempts remain historical pre-public evidence; no public `doc-atlas==1.3.2` release is claimed until the new exact release is published and verified.",
        1,
    )
    prefix = textwrap.dedent(
        f"""\
        # Release identity

        ## Current public candidate

        The current source release candidate is **DocAtlas {VERSION}**. It supersedes the unpublished `1.3.1` candidate because the public-launch README and Official MCP Registry ownership metadata were added after the immutable `v1.3.1` tag.

        Canonical intended identity:

        ```text
        product: DocAtlas
        distribution: doc-atlas
        source version: {VERSION}
        planned immutable tag: v{VERSION}
        maturity: Beta
        MCP Registry name: {SERVER_NAME}
        MCP package: doc-atlas=={VERSION}
        MCP command: uvx doc-atlas=={VERSION} mcp docs-serve
        ```

        No `v{VERSION}` tag or public `doc-atlas=={VERSION}` artifact is claimed by this preparation change. The tag must be created only by the reviewed release-request controller after this launch tree is merged and after the external PyPI Trusted Publisher is corrected. `server.json`, the source version, changelog, and hidden PyPI README ownership marker are kept version-aligned so the exact public package can be verified by the Official MCP Registry.

        The Registry publication path uses GitHub OIDC and runs only after the canonical PyPI publish job and exact Linux/macOS/Windows public-package smokes succeed.

        ## Historical `v1.3.1` publication blocker

        """
    )
    path.write_text(prefix + historical, encoding="utf-8")

    scorecard = ROOT / "docs/public-truth-scorecard.md"
    scorecard.write_text(
        textwrap.dedent(
            f"""\
            # P0 public-truth closure scorecard

            Status: **INCOMPLETE** — `{VERSION}` is the next reviewed source candidate, but no immutable `v{VERSION}` tag or exact public PyPI artifact exists yet. The external PyPI Trusted Publisher mismatch proven by the two historical `1.3.1` attempts must be corrected before publication.

            This document distinguishes proven public truth, pending public evidence, and explicitly accepted operational risk. `accepted_risk` never means that the missing control exists.

            ## Historical publisher evidence

            The immutable annotated `v1.3.1` tag object `77bced8c530c88c57d2e6c5f58cb717bfe837a9f` targets exact reviewed commit `cfa9ab5c365a28d1a4af63afe9f1d53b19532d89`. Canonical workflow run `32587903026` passed build/release gates but PyPI rejected a valid GitHub OIDC token with `invalid-publisher` before upload. A controlled retry produced the same rejection with identical claims.

            The exact records are:

            - [`release-evidence/v1.3.1-publish-attempt-1.json`](./release-evidence/v1.3.1-publish-attempt-1.json)
            - [`release-evidence/v1.3.1-publish-attempt-2.json`](./release-evidence/v1.3.1-publish-attempt-2.json)

            Expected existing-project publisher tuple:

            ```text
            owner: Vanilla1999
            repository: DocAtlas
            workflow: publish.yml
            environment: release-current
            ```

            | Public-truth row | State | Evidence / closure requirement |
            |---|---|---|
            | Release source identity | `pending` | Source version, changelog, README ownership marker, and `server.json` agree on `{VERSION}`. A reviewed release request must create immutable `v{VERSION}` from the exact merged tree. |
            | Branch protection | `accepted_risk` | Maintainer decision remains unchanged: release flow compensates by requiring the tag commit to be reachable from exact remote `main`. |
            | Namespace / state isolation | `green` | Fresh release smoke uses `DOCATLAS_HOME`, `~/.docatlas`, and the `docatlas` MCP registration identity. |
            | Installed agent contract | `green` | The public Docs MCP inventory remains exactly `get_docs_context`, `prepare_docs`, `docs_status`. |
            | Trusted Publisher identity | `pending` | Historical `1.3.1` attempts proved GitHub claims `Vanilla1999 / DocAtlas / publish.yml / release-current`; PyPI still needs that exact publisher under the existing `doc-atlas` project. |
            | Exact public artifact identity | `pending` | Publish exactly `doc-atlas=={VERSION}` and prove gated SHA-256 = PyPI metadata SHA-256 = independently downloaded bytes for one wheel and one sdist. |
            | Exact public MCP behavior | `pending` | No-cache install of `doc-atlas=={VERSION}` must pass the exact three-tool Docs MCP stdio smoke. |
            | Cross-platform public install | `pending` | The exact public package must pass Linux, macOS, and Windows smoke. |
            | Official MCP Registry | `pending` | After all public-package smokes pass, GitHub OIDC publishes `{SERVER_NAME}` version `{VERSION}` and the Registry API must return that exact name/version. |
            | Product claim boundary | `green` | Public maturity remains **Beta**; no Context7 parity or unmeasured product-value claim is introduced. |

            ## Closure rule

            P0 closes only when every `pending` row is replaced by concrete `green` evidence. The `accepted_risk` branch-protection row remains visible. Historical `v1.3.0`/`v1.3.1` tags must never be moved or reused.
            """
        ),
        encoding="utf-8",
    )

    roadmap = ROOT / "roadmap/README.md"
    text = roadmap.read_text(encoding="utf-8")
    start = text.index("## P0.5 — Publish and verify public `1.3.1`")
    end = text.index("## P0.6 — Public-truth closure scorecard", start)
    p05 = textwrap.dedent(
        f"""\
        ## P0.5 — Publish and verify public `{VERSION}`

        `v1.3.0` and `v1.3.1` remain immutable pre-public audit identities whose PyPI OIDC uploads failed before publication. `{VERSION}` is the next public candidate because the launch README, PyPI MCP ownership marker, and Official MCP Registry metadata were added after `v1.3.1`.

        Acceptance:

        - source version, reviewed tag, changelog, wheel, sdist, and `server.json` agree on `{VERSION}`;
        - the PyPI README contains the exact `{SERVER_NAME}` ownership marker;
        - PyPI metadata says Beta and exact public artifact hashes match the gated build;
        - a no-cache install passes the exact three-tool Docs MCP stdio smoke;
        - Linux, macOS, and Windows public-package smokes are green;
        - only then, GitHub OIDC publishes `{SERVER_NAME}` `{VERSION}` to the Official MCP Registry and the exact Registry entry is verified.

        """
    )
    text = text[:start] + p05 + text[end:]
    text = text.replace(
        "Branch protection is the one explicitly accepted residual risk for `1.3.1`;",
        f"Branch protection is the one explicitly accepted residual risk for `{VERSION}`;",
        1,
    )
    roadmap.write_text(text, encoding="utf-8")

    checklist = ROOT / "docs/RELEASE_CHECKLIST.md"
    text = checklist.read_text(encoding="utf-8")
    text = text.replace(
        "Repository `1.2.0` is an unpublished milestone; the next intended public release is `1.3.1` unless a later reviewed release-preparation change supersedes it.",
        f"Repository `1.2.0` is an unpublished milestone; failed `1.3.0`/`1.3.1` tags remain audit history; the next intended public release is `{VERSION}`.",
        1,
    )
    text = text.replace(
        "The executable release decision is reviewable in `.github/release-requests/v1.3.1.json`; its exact base commit, allowed release delta, tag, publisher identity, and public tool inventory are validated before any tag is created.",
        f"A new executable release decision for `.github/release-requests/v{VERSION}.json` must bind the exact merged launch base/delta, tag, publisher identity, and public tool inventory before any `v{VERSION}` tag is created. The old `v1.3.1` request remains audit history.",
        1,
    )
    anchor = "- [ ] Verify the exact public package on Linux, macOS, and Windows for the claimed primary MCP/install surface.\n"
    if anchor not in text:
        raise SystemExit("release checklist platform-smoke anchor not found")
    text = text.replace(
        anchor,
        anchor
        + f"- [ ] The PyPI package README contains `<!-- mcp-name: {SERVER_NAME} -->`, and `server.json` names the exact same server/package version.\n"
        + f"- [ ] After all three public-platform smokes pass, publish `{SERVER_NAME}` to the Official MCP Registry with GitHub OIDC; no Registry PAT/secret is stored.\n"
        + f"- [ ] Query the Registry API and retain exact `{SERVER_NAME}` + release-version evidence.\n",
        1,
    )
    checklist.write_text(text, encoding="utf-8")


def update_tests() -> None:
    path = ROOT / "tests/test_release_state_repair.py"
    text = path.read_text(encoding="utf-8")
    replacements = [
        ('assert __version__ == "1.3.1"', 'assert __version__ == "1.3.2"'),
        ('assert changelog.index("## [1.3.1]") < changelog.index("## [1.3.0]")', 'assert changelog.index("## [1.3.2]") < changelog.index("## [1.3.1]") < changelog.index("## [1.3.0]")'),
        ('assert "for example v1.3.1" in workflow', 'assert "for example v1.3.2" in workflow'),
        ('assert "current source release candidate is **DocAtlas 1.3.1**" in identity', 'assert "current source release candidate is **DocAtlas 1.3.2**" in identity'),
        ('assert "v1.3.0" in identity', 'assert "v1.3.1" in identity'),
        ('assert "no public `doc-atlas==1.3.1` release is claimed" in identity.lower()', 'assert "no public `doc-atlas==1.3.2`" in identity.lower()'),
        ('assert "doc-atlas==1.3.1" in scorecard', 'assert "doc-atlas==1.3.2" in scorecard'),
        ('assert "P0.5 — Publish and verify public `1.3.1`" in roadmap', 'assert "P0.5 — Publish and verify public `1.3.2`" in roadmap'),
    ]
    for old, new in replacements:
        if old not in text:
            raise SystemExit(f"test_release_state_repair.py missing expected text: {old}")
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")

    path = ROOT / "tests/test_patch_release_identity.py"
    text = path.read_text(encoding="utf-8")
    replacements = [
        ('assert __version__ == "1.3.1"', 'assert __version__ == "1.3.2"'),
        ('assert changelog.index("## [1.3.1]") < changelog.index("## [1.3.0]")', 'assert changelog.index("## [1.3.2]") < changelog.index("## [1.3.1]") < changelog.index("## [1.3.0]")'),
        ('assert "current source release candidate is **DocAtlas 1.3.1**" in identity', 'assert "current source release candidate is **DocAtlas 1.3.2**" in identity'),
        ('assert "v1.3.0" in identity', 'assert "v1.3.1" in identity'),
        ('assert "P0.5 — Publish and verify public `1.3.1`" in roadmap', 'assert "P0.5 — Publish and verify public `1.3.2`" in roadmap'),
        ('assert "doc-atlas==1.3.1" in scorecard', 'assert "doc-atlas==1.3.2" in scorecard'),
        ('assert "for example v1.3.1" in workflow', 'assert "for example v1.3.2" in workflow'),
    ]
    for old, new in replacements:
        if old not in text:
            raise SystemExit(f"test_patch_release_identity.py missing expected text: {old}")
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")

    (ROOT / "tests/test_mcp_registry_metadata.py").write_text(
        textwrap.dedent(
            f'''\
            from __future__ import annotations

            import json
            from pathlib import Path

            from docmancer._version import __version__

            ROOT = Path(__file__).resolve().parents[1]
            SERVER_NAME = {SERVER_NAME!r}


            def test_official_mcp_registry_metadata_matches_release_identity() -> None:
                payload = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
                assert payload["$schema"] == "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
                assert payload["name"] == SERVER_NAME
                assert payload["version"] == __version__
                assert payload["repository"] == {{"url": "https://github.com/Vanilla1999/DocAtlas", "source": "github"}}
                assert len(payload["packages"]) == 1
                package = payload["packages"][0]
                assert package["registryType"] == "pypi"
                assert package["registryBaseUrl"] == "https://pypi.org"
                assert package["identifier"] == "doc-atlas"
                assert package["version"] == __version__
                assert package["runtimeHint"] == "uvx"
                assert package["transport"] == {{"type": "stdio"}}
                assert package["packageArguments"] == [
                    {{"type": "positional", "value": "mcp"}},
                    {{"type": "positional", "value": "docs-serve"}},
                ]
                readme = (ROOT / "README.md").read_text(encoding="utf-8")
                assert f"<!-- mcp-name: {{SERVER_NAME}} -->" in readme


            def test_registry_publish_is_oidc_only_and_after_public_platform_smoke() -> None:
                workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
                assert "publish-official-mcp-registry" in workflow
                assert "needs: [public-platform-smoke]" in workflow
                assert "id-token: write" in workflow
                assert "./mcp-publisher login github-oidc" in workflow
                assert "./mcp-publisher publish server.json" in workflow
                assert "releases/download/v1.7.9/mcp-publisher_linux_amd64.tar.gz" in workflow
                assert "ab128162b0616090b47cf245afe0a23f3ef08936fdce19074f5ba0a4469281ac" in workflow
                assert "MCP_GITHUB_TOKEN" not in workflow
                assert "MCP_PRIVATE_KEY" not in workflow
            '''
        ),
        encoding="utf-8",
    )


def main() -> None:
    prepare_readme_and_version()
    write_server_json()
    update_publish_workflow()
    update_release_truth()
    update_tests()


if __name__ == "__main__":
    main()
