# Release identity during P0

Status: active temporary release-truth note for the P0 roadmap reset.

## Current identity

At the 2026-08-21 roadmap reset:

- the latest public PyPI release is `doc-atlas==1.1.1`;
- repository source currently reports version `1.2.0`;
- the repository changelog contains a `1.2.0` milestone, but no corresponding public PyPI release exists;
- current `main` contains substantial work after that milestone.

Therefore repository `1.2.0` is treated as an **unpublished repository milestone**. Current `main` must not be published retroactively as `1.2.0`, because that would make the public artifact contain changes beyond the historical `1.2.0` milestone while reusing the same release identity.

## Next intended public release

The next intended public release is:

```text
doc-atlas 1.3.0
```

The version bump, changelog cut, tag creation, and publication belong to the later P0 release-preparation slice. This roadmap-reset PR deliberately does not change `docmancer/_version.py` and does not create or move a tag.

Before `1.3.0` is published, the following P0 work must be complete:

1. the remote `main` ruleset is active and verified;
2. DocAtlas runtime state/integration identity is isolated from the active `docmancer` product namespace;
3. installed agent guidance matches the real three-tool public MCP contract;
4. release metadata and changelog are cut for `1.3.0` from one protected commit;
5. the exact public wheel and sdist are downloaded and verified byte-for-byte against the gated artifacts;
6. the exact public package passes installed Docs MCP smoke on supported platforms.

## Release claim boundary

The next release remains **Beta**.

Publishing `1.3.0` may establish public artifact/install truth. It must not, by itself, create claims that:

- DocAtlas has Context7 parity;
- autonomous live evidence planning is solved;
- DocAtlas improves real coding-task correctness;
- the product is Stable/Production.

Those are later agent-truth and product-truth decisions.

## Historical identity rule

Existing release tags are immutable evidence. Never move or reuse an existing release tag to make repository history match a later artifact.

If a `v1.2.0` tag exists, preserve it as historical identity and do not publish a different artifact under that version. If it does not exist, do not create one merely to fill the public-version gap. In both cases, `1.3.0` is the next public release candidate after P0 prerequisites are satisfied.
