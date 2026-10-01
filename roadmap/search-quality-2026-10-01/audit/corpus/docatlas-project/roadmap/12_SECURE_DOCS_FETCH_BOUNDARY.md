# Task 12 — secure the Docs remote-fetch boundary

## Priority

P0 security. This PR owns URL/destination policy and per-request transport budgets only. Task 30 owns failure recovery/proxy behavior and suite-wide network hermeticity; task 13 owns whole-job deadlines.

## Problem

The current URL guard rejects literal private IPs but does not establish a complete hostname, redirect, userinfo, response-size, and redaction boundary. A public-looking hostname or redirect can therefore reach a forbidden destination, and raw transport details can leak into later error handling.

## Goal

Create one injectable security boundary that every Docs HTTP request and redirect must pass before bytes are accepted.

## Required implementation

1. Introduce one Docs fetch-policy component used by the real WebFetcher path. It must accept an injectable DNS resolver and clock/byte counters for deterministic tests.
2. Reject URL userinfo and unsupported schemes before constructing a request.
3. Resolve hostnames and reject every answer in loopback, private, link-local, multicast, reserved, unspecified, and configured metadata ranges.
4. Re-resolve/revalidate every redirect target and validate the final response URL; do not trust only the original textual host.
5. Reapply declared host and path allowlists after canonicalization and redirects.
6. Freeze these default per-request budgets in configuration and tests:
   - at most 5 redirects;
   - connect timeout 10 seconds;
   - read timeout 30 seconds;
   - at most 8 MiB transferred per response;
   - at most 16 MiB decoded/extracted text per response.
7. Reject disallowed content types before expensive extraction. Preserve existing supported HTML/Markdown/text formats explicitly.
8. Return a typed internal safe cause containing category and redacted URL. Redact URL credentials, query secrets, proxy credentials, tokens, and sensitive headers before any public/persisted representation.
9. Keep the original exception only in a private diagnostic chain that cannot be serialized accidentally.

## Required deterministic fixtures

- hostname resolving to private space;
- public first answer followed by private DNS rebinding;
- public URL redirecting to loopback/metadata address;
- cross-domain and disallowed-path redirect;
- too many redirects;
- oversized transfer and oversized decoded text;
- unsupported content type;
- URL/proxy credentials in a thrown exception;
- one allowed official-source request through an injected transport.

Do not call public DNS or sockets in these tests.

## Non-goals

- Do not change the job queue, whole-job deadline, retry cache, or persisted job schema.
- Do not migrate Packs in this PR.
- Do not add browser crawling or private-network source support.

## Acceptance criteria

- All listed SSRF, redirect, rebinding, budget, and redaction fixtures pass through the real Docs policy/fetch boundary.
- No rejected response reaches extraction or staging.
- No secret-bearing raw exception is serializable through the boundary.
- Existing allowed public-source behavior is preserved with the injected transport.
- Focused security tests and `git diff --check` pass.
