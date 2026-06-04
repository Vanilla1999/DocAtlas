# 00 — Сводный roadmap развития Docmancer

## Стратегия

Рекомендуемое позиционирование:

> **Docmancer is a local, version-aware docs runtime for coding agents.**

Docmancer Docs должен быть главным продуктовым narrative. Docmancer Packs стоит оставить вторым advanced-продуктовым слоем под тем же брендом, но не делать его hero story.

## Главный риск

Самый большой риск — не недостаток фич, а потеря доверия из-за непредсказуемого agent UX:

- registered docs могут требовать ручной `docs_url`;
- агент может уйти в direct WebFetch;
- source/version exactness не всегда явны;
- user-facing CLI/DX может показывать инфраструктуру раньше ценности.

## Главный первый milestone

**Milestone 1: Registered docs query without manual docs_url.**

Цель:

```text
get_library_docs({ library, topic })
  -> internal registry resolve
  -> use stored docs_url/source locator
  -> query local index
  -> return source-grounded context pack
```

Для already registered docs `needs_docs_url` больше не должен появляться.

## Приоритетные эпики

| Priority | Epic | Почему сейчас |
|---:|---|---|
| 1 | Agent-proof MCP Docs UX | Закрывает конкретный live failure: `needs_docs_url` → WebFetch |
| 2 | Registry / Source Identity | Даёт data model для stable source/version resolution |
| 3 | Product Positioning / Docs vs Packs | Убирает product narrative split |
| 4 | Project-aware Version Resolution | Делает сильный wedge: docs под реальные версии проекта |
| 5 | Retrieval Quality / Eval / Observability | Делает качество измеримым, а не demo-only |
| 6 | First-run DX / Doctor | Снижает activation friction и support burden |

## 30 / 60 / 90 дней

### Первые 30 дней

Must-have outcomes:

- `get_library_docs` auto-uses stored `docs_url` для unique registered sources.
- `needs_docs_url` ограничен genuine unknown/unrenderable sources.
- Появился shared resolver или минимум unified resolve path для `get_library_docs` / `resolve_library_id`.
- Есть regression tests на registered web docs without `docs_url`.
- README/product narrative разделяет Docs и Packs.

### 60 дней

Must-have outcomes:

- Registry source identity model введена или частично backfilled: `source_id`, `canonical_id`, `requested_version`, `resolved_version`, `docs_snapshot_exact`.
- Project-aware path production-hardening для Flutter/Dart.
- Начат Rust или другой deterministic ecosystem pilot.
- Есть initial eval dataset и `--explain-json` / trace artifact MVP.
- `doctor` начал показывать action-oriented remediation по топовым failure modes.

### 90 дней

Must-have outcomes:

- Три polished demo scenarios:
  1. registered web docs query feels local;
  2. project-aware dependency docs;
  3. private/local docs to compact context pack.
- Есть CI soft gates по retrieval/eval baseline.
- First-run quickstarts разделены по lanes: Local Docs, Versioned MCP Docs, Action Packs.
- Beta/GA gate может оцениваться через grounded docs sessions, registered-source success rate, attribution/version correctness.

## What not to do yet

- Не делать Packs hero narrative.
- Не строить hosted query plane.
- Не начинать universal docs discovery для npm/Python до стабилизации registry identity.
- Не внедрять LLM-as-judge как основной eval gate.
- Не добавлять dashboard/TUI раньше понятного CLI/doctor output.
- Не менять весь registry schema одним большим PR без compatibility plan.

## North Star

**Weekly Grounded Docs Sessions** — weekly sessions, где Docmancer отдал useful docs answer из registered/indexed source с source metadata и без ручного обхода через `docs_url` / WebFetch.

Supporting metrics:

- registered-source success rate;
- median MCP calls to useful answer;
- direct WebFetch fallback rate for registered docs;
- version correctness;
- attribution accuracy;
- time-to-first-success;
- token compression ratio without quality loss.
