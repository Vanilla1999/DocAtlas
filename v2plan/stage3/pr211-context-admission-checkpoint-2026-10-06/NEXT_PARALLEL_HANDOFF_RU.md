# Продолжение после compaction: identity / admission / corpus contract

2026-10-07. **План, не запущенное исполнение. Full dictionary exit NOT DONE.**

## Baseline и состояние

- Опубликованный commit `9488cb66`, ветка `integration/stage3-v2-identity-pr1`.
- Открытый PR: https://github.com/Vanilla1999/DocAtlas/pull/211 . Merge не выполнялся.
- Последний completed slice: [DISCOVERY_LEGACY_EXIT_RU.md](DISCOVERY_LEGACY_EXIT_RU.md).
- 1431 new dictionary-exit tests PASS, stdio MCP smoke PASS, frozen pins 13/13 совпали.
- Technical combined 1476 PASS / 1 preserved FAIL; old selector 25 PASS / 57 FAIL.
  Остальные mixed reds см. reports; результаты не waived и не full CI.
- Self-host quality FAIL: [report](archives/dictionary-exit-discovery-legacy-self-host-v1.json).
- Current completed-slice pins: [manifest](archives/dictionary-exit-discovery-legacy-source-manifest.json).
- Raw `archives/p2-real-mcp-alias-ablation-v1.json.gz` остаётся локально вне Git;
  не добавлять/не удалять. Historical source manifests и frozen artifacts не менять.
- Все исполнители/reviewers предыдущего этапа завершены. Новый этап ещё не запущен.

## Источники по организации агентов

Прочитаны онлайн 2026-10-07:

1. OpenCode V2 Agents: https://opencode.ai/v2/docs/agents . Subagents имеют fresh
   context, foreground/background и собственные permissions; reviewer может быть
   read-only. Подтверждено также Context7 `/websites/opencode_ai_v2`.
2. Anthropic multi-agent engineering:
   https://www.anthropic.com/engineering/multi-agent-research-system . Orchestrator
   задаёт каждому worker цель, output format, границы и budget; независимые задачи
   параллелятся. Статья явно предупреждает: coding dependencies хуже параллелятся,
   координация и token cost могут съесть выигрыш. Research metrics не доказательство
   ускорения этого coding проекта; обещаний процента ускорения нет.
3. OpenAI Codex Worktrees: https://developers.openai.com/codex/environments/git-worktrees .
   Изолированные checkout позволяют работать без пересечения файловых изменений.
   Это общий Git принцип, не утверждение, что OpenCode автоматически создаёт worktrees.

## Рекомендуемая схема: 2 implementers + 1 read-only auditor

Один parent coordinator интегрирует и публикует. Reviewer не является автором
собственных production fixes. По мере готовности независимое review можно запускать
параллельно с работой другого worker, но только на завершённых/зафиксированных slices.

### A — source identity и preference cleanup

Exclusive production ownership:
- `docmancer/docs/curated_sources.py`;
- `docmancer/docs/dart_official_docs.py`;
- `docmancer/docs/application/_library_docs_service_part01.py`.

Задачи:
- Удалить nonliteral ecosystem mapping, не выдавать framework/package-manager label
  за точный source identity и не переносить aliases в config/JSON/prompts.
- Удалить knowledge-based official-host preference, оставить явную source policy,
  deterministic structural/literal ranking и scope/version/network barriers.
- Разобрать `firebase_firestore`→`cloud_firestore`: без подтверждённого explicit
  identity contract не возвращать документацию другой библиотеки. Не придумывать URL
  замены. При необходимости fail closed и сохранить compatibility regression.

Не owned: curated JSON, filtering/github/discovery pipeline и common projection.
Если нужно менять contract/registry вне allocation — report parent, не silent edit.
Новые files: `test_dictionary_exit_source_identity.py`, отдельный diagnostic shard,
отчёт `SOURCE_IDENTITY_DICTIONARY_EXIT_RU.md` в этом checkpoint.

### B — core/admission helper exit

Exclusive production ownership:
- `docmancer/docs/domain/question_plan_core.py`;
- `docmancer/docs/domain/admission_contract.py`;
- `docmancer/docs/domain/admission_local_binding.py`;
- `docmancer/docs/domain/admission_meaning.py`.

Задачи:
- Классифицировать оставшиеся NL helpers/coverage-gap conjunction rules и legacy
  admission fallback. Убрать guessed semantic credit, сохранить DTO/ABI, exact
  source spans и explicit unresolved/negative results.
- Сохранить narrow literal evidence без universal supported/valid/empty-all-pass.
- Проверять direct-call и реально вызываемые consumers отдельно: imports не
  доказывают default execution. Не менять frozen ownership registry ради зелёных tests.

Не owned: grammar enums, question_ownership, selector/projection, answer-unit files.
Новые files: `test_dictionary_exit_admission_literals.py`, отдельный diagnostic shard,
отчёт `ADMISSION_LITERAL_DICTIONARY_EXIT_RU.md`.

### C — read-only corpus contract / остаточный inventory audit

Production edits запрещены. Изучить:
- `docmancer/connectors/fetchers/pipeline/filtering.py`;
- `docmancer/connectors/fetchers/github.py`;
- discovery/web/crawl4ai callers и существующие source-policy/config boundaries;
- `docmancer/docs/domain/source_map.py` и `docmancer/docs/domain/project_state.py` topic fallback.

Результат — новый `CORPUS_CONTRACT_OPTIONS_RU.md`: exact current membership, какие
locale/topic/GitHub exclusions ещё semantic, какие технические, какие callers
разрешают explicit URLs/paths/version/include_generated. Предложить минимальный
explicit bounded contract без расширения hosts/pages/locales или relocation словарей.
Если нужен owner decision — перечислить варианты и последствия, НЕ внедрять выбор.
Source-map suffix priorities и topic fallback классифицировать отдельным leftover.

Corpus exclusion removal остаётся BLOCKED до решения о membership. Это не работа
для третьего свободно редактирующего агента. Не обещать full exit после A/B/C.

## Изоляция и handoff каждого worker

- Предпочтительно отдельные worktrees от одного verified baseline `9488cb66` под
  `/tmp/opencode/`, с уникальными ветками/checkout. Создание — только при запуске,
  не применять старые executor worktrees и patches повторно.
- Явные непересекающиеся file allowlists обязательны и при worktrees. В primary
  пишет только coordinator; common consumers интегрируются последовательно.
- Свежий worker получает baseline SHA, paths/checkpoints, цель, запреты, tests,
  критерии завершения. Не рассчитывать на память родительской беседы.
- Worker сдаёт file list + diff/patch относительно baseline, фактические test counts,
  red nodes, remaining dependencies и компактный report. Без commit/push/network
  в primary. Temporary logs не единственная provenance.
- Не считать частичный overlay полноценным clean-baseline сравнением.
- Не порождать бесконечные secondary slices: новые находки вне ownership записать
  в OPEN. Новый allocation только coordinator; phase закрывается bounded результатом.

## Acceptance и публикация

1. Перед стартом проверить git status, HEAD/origin и source pins. Не discard user work.
2. New tests с normal conftest и новыми hash-bound diagnostic shards; existing
   tests/gold/thresholds/224 frozen cases не менять. Никакого `--noconftest` acceptance.
3. После готовности A/B — independent read-only reviews и original repro/negative
   probes. При блокере сначала fix, потом повторный review; не править reviewed slice
   конкурентно с reviewer.
4. Coordinator интегрирует последовательно и запускает ВСЕ dictionary-exit tests,
   technical/old mixed suites, actual indexed MCP и stdio smoke. Reds сохраняются.
5. Снять новый versioned self-host report и source manifest; старые не перезаписывать.
   Full source/provenance и mutation authorization не заменяются local DTO equality.
6. Staged diff check и review, затем commit/push текущей PR ветки без force и без merge.
7. Dictionary removal completion и retrieval-quality acceptance — разные gates.
   После remaining audit/contract decisions полнота улучшается общими механизмами,
   не возвращением topic dictionaries. Full CI/rebuilt package остаются отдельными.

**Сейчас:** только подготовка handoff. Production изменений/новых агентов этим планом
не запускать автоматически; начать после следующего явного продолжения пользователя.
