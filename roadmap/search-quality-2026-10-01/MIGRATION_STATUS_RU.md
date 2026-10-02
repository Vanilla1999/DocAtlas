# Статус миграции языковых зависимостей

## Этапы

| Этап | Статус | Что требуется для закрытия |
|---|---|---|
| M0 | Закрыт: inventory | 58 static call sites, reviewed callbacks, guard ownership, controlled public branch trace; см. M01_ACCEPTANCE_RU.md |
| M1 | Закрыт: совместимый extraction | baseline и isolated M1: одинаковые 211 passed / 1 known failure; три packet/snapshot hashes совпали; см. M01_ACCEPTANCE_RU.md |
| M2 | В работе, gate не пройден | httpx-07 исправлен; cross-stage controls: 247 passed. Последний полный docs: 3355 passed / 108 failed; 26 общие с checkpoint, 82 current-only. Другие native delivery regressions и legacy fixture migration открыты |
| M3 | Не начат | выбрать и зафиксировать multilingual retrieval candidate, corpus/protocol и измерить recall/precision/cost |
| M4 | Не начат | read-only qualification migration после M3; восстановить regression шага 07 и проверить actual public packet |
| M5 | Не начат | удалить obsolete callers/rules только после migration; security/certification отдельно |
| M6 | Не начат | installed MCP, реальные host ответы и независимый holdout |

Checkpoint плана: `d521b358`; M0/M1 и первые M2 slices закоммичены `5a732198`.
Explicit-only M2 изменения пока незакоммичены. Opt-in compatibility отклонена:
отсутствующие intent/lifecycle теперь означают read/current, а не NL inference.
Push/merge не выполнены. Шаг 07 открыт; шаг 08 не начат.

## Следующее действие по порядку

M0/M1 закрыты в scope исходного плана, результаты в `M01_ACCEPTANCE_RU.md`.
Следующее — M2. Baseline equivalence M1 отделена от M2 через isolated worktree.
Не продолжать mechanical regex replacement вместо общего relevance решения.

Последний завершённый расширенный прогон: `m2_no_legacy_final.log` (547 tests).
Открыты `httpx-07` (потеря документированного timeout факта),
`test_added_text_gets_policy_check_not_only_seed` и два порядка
`test_more_citations_cannot_outvote_completion_of_a_seed`.
Их assertions не ослаблены и explicit lookup в исходный public request не добавлен.
Первый полный запуск `tests/docs` был прерван timeout 120 s. Повторный завершён:
`m2_docs_regression.log`, **3174 passed / 284 failed**, 157.16 s. Этот прогон
предшествует последнему exact-anchor fix и не является зелёной приёмкой.
В failures есть retired-need fixture dependencies, delivery/source controls,
CLI anchors и 8 namespace-isolation errors (`uid_map: Operation not permitted`).
Не все падения классифицированы; автоматически исключать их из gate нельзя.
Следующий ограниченный разбор — attribution/selection на этих четырёх случаях;
не восстанавливать EN/RU aliases и не удалять admission/source guards ради PASS.
Диагностика `m2_httpx07_diagnostic.json`: исходный public request сохранён,
`context_pack` уже пуст до final projection; recovery сообщает `no_candidates`.
Это локализация потери, не доказательство её первопричины и не M3 experiment.
Дополнительная инструментированная диагностика: project retrieval возвращает
пять chunks с `insufficient_visible_match`; последующая доставка их теряет.
Focused M2 boundary gate после exact-anchor fix: **353 passed**,
`m2_boundary_acceptance.log` (включая exact-document fallback controls).
Окончательное закрытие требует согласовать отличие boundary acceptance от
оставшихся downstream delivery regressions; автоматически переносить их в
M4 или менять scope M2 ради закрытия не разрешено.

Групповой разбор вместо исправления отдельных assertions:
`M2_REGRESSION_GROUPS_RU.md`. Спорное CLI `=`/numeric правило отменено;
literal boundary — 125 passed, admission controls — 150 passed, patch/owner
caller controls — 41 passed (наборы пересекаются, не суммировать).
Повторный полный regression: `m2_docs_regression_after_groups.log`, завершён:
**3323 passed / 137 failed**, 161.80 s. 8 failures — namespace limitation,
остальные не объявлены obsolete или baseline без разбора. Joint invariant
failures предыдущего прогона исчезли после восстановления technical anchors,
без изменения исходного fixture или ослабления assertions; `httpx-07` остаётся.

Начат согласованный retirement: `M2_RETIREMENT_BATCH01_RU.md`.
Удалены 9 pure generation cases; source/span/coverage controls сохранены через
explicit fixtures или original/exact-anchor isolation. Текущий batch:
154 passed / 4 failed (256-token public coverage controls оставлены).
Полный regression после batch не повторён; M2 не закрыт.

Последующий серьёзный разбор: `M2_CRITICAL_REVIEW_RU.md`. Исправлены превышения
size/catalog budgets без изменения hard limits или source guards. Изолированный
checkpoint `5a732198`: 3461 passed / 50 failed. Current stable:
`m2_serious_stable_docs.log`, 3341 passed / 110 failed. `httpx-07` — current-only
failure. Ранние отчёты выше являются историей, не актуальной приёмкой.
В index внесены новый typed helper и intentional retirement deletions для
корректной runtime inventory проверки; commit пока не создан.

Уточнение по свежему native сравнению: `M2_HTTPX_CAUSAL_REVIEW_RU.md`.
Current httpx-07 доставляет контекст, но не required абзац; он отсутствует уже
на входе tagging. Checkpoint находил его через удалённые generated probes,
а original query отвергал даже там (3/14 body matches). Предыдущая локализация
«пусто до projection» историческая. Focused controls: 115 passed / 1 failed.
Простое добавление explicit lookup в diagnostic request факт не восстановило.
Нужен отдельный разбор discovery cap/ranking плюс downstream qualification;
одно снижение ratio или возврат aliases не являются допустимым fix.

Последующий согласованный cross-stage fix: `M2_CROSS_STAGE_FIX_RU.md`.
httpx-07 восстановлен на исходном public request без generated probes:
prose punctuation correction, indexed-parent diversity в прежнем quota и
literal anchor cross-check только когда нет independently qualified public
candidates. Original coverage из anchor не выводится, thresholds/limits/source
guards не ослаблены. Causal ablation: отдельное отключение каждого fix снова
теряет required абзац; private value не доказан, answer_supported/edit_ready=False.
Controls: 247 passed; retrieval guards: 82 passed; final safety: 66 passed
(не суммировать пересекающиеся suites).
Последний полный run: `m2_cross_stage_stable_docs.log`, 3355 passed / 108 failed.
Новых failing IDs относительно предыдущего stable run нет. Ранние утверждения
о текущем httpx-07 failure выше исторические. Открыты, в частности, native
delivery mkdocs-05/pydantic-07/ruff-07 и миграция guard fixtures с generated rows.
M2 не закрыт; M3/M4 stages не объявлены начатыми/завершёнными по этому локальному
fix. Commit/push/merge не выполнены.

По последующему запросу выполнен analysis-only групповой разбор:
`M2_GROUP_DEPENDENCY_ANALYSIS_RU.md`, native captures в
`m2_group_dependency_analysis.json` и независимые literal-topic controls в
`m2_group_synthetic_controls.json`. Для двух plain-language partial requests
required текст переживает retrieval quota, но rerank сокращает 6 candidates до
0 из-за пустых qualified IDs. Поздний read-context fallback лишён inputs.
Это подтверждённая общая prefit/disposition зависимость, не предложение менять
вопросы. Отдельно подтверждена потеря другого witness до qualification на cap.
Следующий участок — единый source/context/support disposition до prefit,
с раздельным discovery контролем. Production в этом analysis шаге не менялся.

### Последующий общий read-context fix

По разрешению пользователя реализован shared prefit/final read-context admission:
`M2_READ_CONTEXT_ADMISSION_FIX_RU.md`. Он проверяет original-byte binding,
source/reference/constraint guards и локальный lexical context witness, не
порождая generated probes, qualified IDs или permissions. Native pydantic/ruff
partial passages восстановлены на исходных requests; отдельный mkdocs cap loss
остаётся. Последний полный `tests/docs`: **3382 passed / 104 failed**, новых
failing IDs к stable baseline нет, восстановлены четыре существовавших failures.
Новые controls — 23 passed. Log: `m2_read_context_admission_docs.log`.
M2 по-прежнему открыт; это не приёмка всех оставшихся failures.

Для M3 нужны фиксированные model/provider, доступность execution environment и
стоимость. Без actual retrieval/model runs нельзя выдавать локальные pytest PASS
за multilingual quality или host correctness. Эти решения не скрывать за default
активацией или непроверенным semantic threshold.

Сохранённый baseline self-host failure `flow_mcp` остаётся открытым, даже когда
локальные guard regressions проходят. Старые незакоммиченные installed wires
шага 07 не восстановлены: история разговора не является заменой raw artifacts.
