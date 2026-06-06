# 01 — Agent-proof MCP Docs UX Plan

## Цель

Сделать MCP docs UX устойчивым для LLM-agent:

> Если docs source уже зарегистрирован, `get_library_docs({ library, topic })` должен сам найти source в registry, использовать stored `docs_url` / locator и вернуть context pack без ручного `docs_url`.

## Проблема

Live failure:

1. Web docs target был проиндексирован.
2. `get_library_docs` вызвали с `library` + `topic`, но без `docs_url`.
3. Tool вернул `needs_docs_url`.
4. Агент ошибочно ушел в direct WebFetch, хотя docs уже были локально indexed.

## Core decisions

| Decision | Смысл |
|---|---|
| `get_library_docs` делает internal resolve | Caller не обязан предварительно вызывать `resolve_library_id` |
| `docs_url` становится registry-owned | После регистрации caller не обязан помнить URL |
| `needs_docs_url` только для genuine miss | Registered source never asks for same URL again |
| Ambiguous responses возвращают candidates | Агент не гадает между версиями/sources |
| Blocking warnings имеют next actions | LLM получает executable remediation |
| Success with warning is still success | Non-blocking warnings не должны провоцировать fallback |
| Response declares anti-WebFetch policy | Agent guidance становится machine-readable |

## MVP scope

### Must

- `get_library_docs` вызывает shared/internal resolver.
- Unique registered source выбирается автоматически.
- Stored `docs_url` / locator используется без caller input.
- `needs_docs_url` не возвращается для registered web docs.
- Unknown library без `docs_url` всё ещё получает blocking remediation.
- Ambiguous registered sources возвращают candidates и retry patches.
- Success response включает effective identity/source metadata.
- Добавлены regression tests.

### Should

- Добавить machine-readable envelope минимум для `get_library_docs` и `resolve_library_id`.
- Добавить `policy.direct_webfetch` в structured result.
- Зеркалить structured JSON в text для старых MCP clients.
- Обновить tool descriptions и skill instructions.

### Could

- Full schema v2 для всех docs tools.
- Detailed resolver trace.
- Rich `inspect_library_docs` output.
- Telemetry for WebFetch escape rate.

## Target behavior

### Registered unique source

Input:

```json
{
  "library": "flutter-adaptive-responsive",
  "topic": "breakpoints"
}
```

Expected:

- `status=success`;
- `isError=false`;
- `docs_url_source=registry`;
- warning `used_registry_docs_url` may be info/non-blocking;
- no `needs_docs_url`;
- policy says direct WebFetch is forbidden/discouraged because registered source exists.

### Unknown library

Expected:

- `status=needs_input` or `unknown_library`;
- blocking warning `needs_docs_url` / `needs_registration`;
- `next_actions` explains `prefetch_library_docs` or retry with `docs_url`;
- direct WebFetch only `discovery_only`, not answer path.

### Ambiguous source/version

Expected:

- `status=ambiguous`;
- `candidates[]` with `source_id` / `canonical_id`;
- `arguments_patch` for retry;
- direct WebFetch forbidden because registry candidates exist.

## Minimal response envelope

For MVP do not overbuild full schema for every tool. Start with:

```json
{
  "tool": "get_library_docs",
  "schema_version": "2.0-mvp",
  "status": "success | needs_input | ambiguous | error",
  "decision": "answer_returned | retry_same_tool | choose_candidate | call_other_tool | stop",
  "request": {
    "input": {},
    "effective": {}
  },
  "identity": {
    "source_id": null,
    "canonical_id": null,
    "library": null,
    "ecosystem": null,
    "version": null,
    "docs_url": null,
    "docs_url_source": null,
    "selected_by": null,
    "docs_snapshot_exact": null
  },
  "policy": {
    "direct_webfetch": "forbidden | discovery_only | allowed",
    "reason_code": "registered_source_exists | registry_candidates_exist | no_registered_source"
  },
  "diagnostics": {
    "warnings": []
  },
  "next_actions": [],
  "result": null,
  "candidates": []
}
```

## Warning codes

| Code | Blocking | Use |
|---|---:|---|
| `used_registry_docs_url` | no | Stored URL was used |
| `needs_docs_url` | yes | Truly unknown/unrenderable source |
| `needs_registration` | yes | Source must be registered/prefetched |
| `ambiguous_library` | yes | Multiple library/source matches |
| `ambiguous_version` | yes | Multiple versions match |
| `using_latest` | no | Default/latest selected |
| `not_exact_snapshot` | no | Moving channel/site |
| `stale_docs` | no, if cache usable | Docs stale but usable |
| `docs_url_conflict` | yes | Caller passed conflicting URL |

## Acceptance criteria

| Criterion | Target |
|---|---:|
| Registered web docs query without manual `docs_url` | 100% |
| `needs_docs_url` emitted for registered source | 0 |
| Happy path MCP calls to useful answer | ≤ 1 |
| Ambiguous responses include candidates | 100% |
| Blocking responses include next actions | 100% |
| Success responses include effective identity | 100% |

## First regression tests

1. `registered_web_docs_without_docs_url_returns_success`
2. `registered_web_docs_does_not_emit_needs_docs_url`
3. `registered_web_docs_uses_registry_docs_url`
4. `unknown_library_without_docs_url_returns_needs_docs_url`
5. `ambiguous_versions_return_candidates`
6. `ambiguous_versions_include_retry_patches`
7. `success_response_includes_effective_identity`
8. `success_with_registry_docs_url_has_non_blocking_warning`

## Implementation sequence

1. Locate current `get_library_docs` and docs registry resolver.
2. Add failing tests for registered web source without `docs_url`.
3. Extract or implement internal resolver function.
4. Refactor `get_library_docs` to call resolver before `needs_docs_url` logic.
5. Use stored `docs_url` / locator when resolver returns unique registered source.
6. Add minimal structured diagnostics/identity output.
7. Add ambiguity response path.
8. Update MCP tool descriptions and agent skill guidance.

## Non-goals for first PR

- Full registry schema migration.
- Full source_id/canonical_id migration.
- Full docs tools response schema v2.
- Project-aware npm/Python/Rust/Go expansion.
- Observability dashboard.
