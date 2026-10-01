# MCP runtime threat model

Status: security boundary for the Docs server and advanced MCP Packs gateway.

## Assets

- credentials resolved for installed packs;
- local project files and documentation indexes;
- installed pack artifacts and manifest grants;
- outbound network access;
- agent trust in MCP tool results.

## Trust boundaries

1. Pack metadata and artifacts are untrusted until their recorded hashes are
   verified.
2. Operation arguments are untrusted and must pass the operation schema.
3. Remote HTTP targets and redirects are untrusted.
4. Python pack execution is trusted only after explicit `--allow-execute`
   opt-in. It is process isolation with a reduced environment, not a sandbox.
5. Documentation content is evidence and can contain misleading instructions;
   source attribution does not make content safe.

### Documentation instruction-trust contract

- Source provenance, version exactness, repository authority and instruction
  trust are independent dimensions. Exact official documentation remains
  untrusted document data.
- Ordinary repository Markdown is cited data. Only explicit agent policy files
  inside the configured repository authority receive scoped policy status, and
  they cannot override system, user, tool or runtime safety policy.
- Returned document content is delimited from generated warnings, metadata and
  typed next actions. Indexed prose never selects `prepare_docs`, network,
  filesystem, shell or credential actions.
- Instruction-like pattern detection is warning-only telemetry. It is not a
  sanitizer or proof of safety, and matched content remains retrievable.
- Host models must cite document content as evidence rather than execute it as
  policy.

## HTTP controls

- Only declared operation hosts are allowed.
- HTTPS is required unless a grant explicitly permits HTTP.
- URL userinfo is rejected so credentials cannot be embedded in targets.
- Private, loopback, link-local, multicast, unspecified and reserved addresses
  are blocked unless a grant explicitly permits private networking.
- DNS answers validated before credential construction are passed to the
  executor. If the answer set changes before execution, the request fails with
  `dns_resolution_changed`.
- Redirects are never followed automatically.
- Responses are streamed and bounded by `max_response_bytes`; declared
  Content-Length and decoded streamed bytes are both checked.
- Timeouts are bounded for connect, read, write and pool acquisition.

## Residual DNS risk

DocAtlas checks DNS before dispatch and again immediately before the HTTP
request. The final socket resolution is owned by the HTTP client, so this is not
cryptographic DNS pinning. A deployment that treats DNS or the local network as
hostile must also enforce an outbound firewall/proxy policy that blocks private
and metadata ranges. Do not describe the current control as complete DNS
rebinding prevention.

## Python executor limitations

The Python executor:

- is disabled unless installation explicitly allows execution;
- restricts the declared import module;
- removes inherited credentials and most environment variables;
- does not automatically use a project virtual environment;
- blocks a small set of direct network-module imports.

It does not provide filesystem, syscall, subprocess or complete network
isolation. Malicious Python code can use alternate modules or subprocesses.
Only install executable packs from trusted sources. Strong isolation requires a
container or OS sandbox and is outside the current runtime guarantee.

## Non-goals

- proving that an installed executable pack is benign;
- making documentation immune to prompt injection;
- proving a patch safe to merge;
- replacing host-level egress controls or secret management.

## Required regression coverage

Security changes must cover host allowlists, URL userinfo, IPv4/IPv6 private
ranges, DNS answer changes, redirects, streamed and compressed response limits,
artifact tampering, destructive gates and executable-pack opt-in.
Documentation-boundary coverage must include fake policy messages, tool-call
requests, credential exfiltration text, instructions in code/comments and a
legitimate imperative tutorial that remains retrievable.
