# Task 30 — preserve network failures and make retry/tests deterministic

## Priority

P0 reliability after task 12. This PR owns transport failure taxonomy, proxy recreation, negative-cache behavior, and accidental outbound test calls.

## Problem

The real WebFetcher can flatten HTTP client exceptions into `None`, `ValueError`, or later extraction failures. A VPN/proxy transition is therefore misdiagnosed, and a failed transport/discovery result may influence the next identical request. Separately, default tests can resolve public hosts or contact an optional hosted registry, so ambient SOCKS/VPN settings change results.

## Goal

Preserve safe network causes end-to-end and prove that the same process recovers after connectivity changes while the default suite performs no unmocked outbound access.

## Required implementation

1. Map real transport causes to stable codes: `dns_failure`, `network_unreachable`, `connect_timeout`, `read_timeout`, `tls_failure`, and `http_failure`. Keep extraction/indexing errors separate.
2. Preserve `phase`, redacted `failed_url`, HTTP status when safe, and `retryable`; never rewrite a transport failure as `not_found`.
3. Do not persist/cache retryable discovery/network failure as a negative source result.
4. Create a fresh client/transport attempt for a retry job so changed proxy, DNS, certificate, or route settings are observed in the same MCP process.
5. Make environment-proxy use explicit. If a configured SOCKS URL lacks optional transport support, return `proxy_configuration_error` rather than failing unrelated client construction.
6. Add one deterministic local/custom-transport state machine: first identical request fails as unreachable, connectivity flips, second succeeds without restarting service/MCP or clearing registry/cache.
7. Add a default-test guard that rejects unregistered outbound DNS/socket/HTTP access. Live tests must carry an explicit marker and remain outside default CI.
8. Remove accidental network from Packs/registry tests by injecting a local registry/transport or disabling hosted fallback in test configuration. Do not redesign Packs behavior.

## Files to inspect first

- `docmancer/connectors/fetchers/web.py`
- library refresh/error classification code
- HTTP client factories
- `docmancer/mcp/registry.py`
- tests that use `example.com` or optional hosted artifacts

## Required tests

- each real HTTP client exception class maps to its code and safe fields;
- offline-to-online identical retry succeeds in one service and one MCP process;
- retry performs a new transport attempt and no negative cache blocks it;
- ambient `ALL_PROXY=socks5h://...` produces either supported behavior or one clear configuration error;
- the default test suite's outbound guard catches an intentionally unmocked request;
- existing local MockTransport tests no longer need public DNS.

## Non-goals

- Do not implement job persistence/deadlines.
- Do not require a VPN or public internet.
- Do not weaken destination security from task 12.

## Acceptance criteria

- Network, extraction, indexing, and true `not_found` remain distinguishable through the public job response.
- Same-process recovery fixture passes without cache/registry cleanup.
- Default CI performs zero unmocked outbound calls and behaves consistently with proxy variables set or unset.
- Focused network/registry tests and `git diff --check` pass.
