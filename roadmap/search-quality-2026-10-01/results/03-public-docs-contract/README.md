# Шаг 03 — текущий публичный docs contract

Baseline: `11ee5dbe`. Исправлены только текущие инструкции, добавлены regression tests; runtime и historical audit не менялись. Результат и [саморевью шагов 03–04](REVIEW_RU.md) включены в общий коммит по запросу пользователя; push/merge не выполнялись.

## Подтверждённые противоречия и правки

| Страница | До | После |
|---|---|---|
| `wiki/Architecture.md` | legacy direct job tools; tracker назван in-memory | текущие `docs_status(action="job"/"jobs")`, `prepare_docs(action="cancel_docs_job")`; SQLite persistence default runtime |
| `docs/mcp-docs-server.md` | polling без обязательного action; project answer proof объявлен условием ответа | exact polling call; project reads — retrieval-only; host объясняет факты из `sources` через `evidence_id`, без edit/completeness permission |
| `SKILL.md` | ссылка на unbounded `next_action`; cancellation route не указан | bounded recommended action; текущий cancel route; public evidence и false certification flags |
| `wiki/Troubleshooting.md` | hybrid безусловно падает назад на lexical | fail-closed; degraded output только с explicit `--allow-degraded`, не semantic success |

`docs/source-continuation.md`, `docs/AGENT_DOCS_WORKFLOW.md`, `wiki/Configuration.md` уже согласованы с этими условиями; проверены, не переписаны. Исторические ADR/analysis/research и архив не редактировались.

Опора на source: текущие advertised ToolSpecs (`current_tools`, сохранены в control provenance), default service construction с DB-backed DocsJobTracker, `tests/test_retrieval_features.py` (capability failure/degraded opt-in), `tests/docs/test_mcp_output_contract.py`, maintained source-continuation/agent workflow. Новая policy не выбрана: исправлен drift к существующему contract.

## TDD и контрольные запросы

- [Red](red.log): 4 новые tests падают на исходных инструкциях.
- [Green](green.log): **45 passed** — новый docs-contract module, self-host agent contract, public output contract и retrieval-feature controls. Тесты валидируют job/cancel arguments против advertised schemas, не выдуманного tool inventory.
- [Runner](run_controls.py) синхронизировал отдельный fixture из семи текущих страниц и сохранил original questions Q11/Q12/Q14/Q25/Q26 **обоих** projectA/projectB наборов: [финальный provenance](controls-final/provenance.json), 10 packets. Первый прогон `controls/` сохранён отдельно; финальный учитывает уточнение default persistent tracker versus explicit in-memory injection. Проверены verbatim snippets и отсутствие answer/edit certification. Это Python public-router consistency probe; docs-only изменение не требует новой runtime installed-stdio правки.

## Ручная проверка final packets: ограничения не скрыты

| Контроль | Реально доставлено |
|---|---|
| A-Q11 | clean project sync есть; отличие external refresh отсутствует — partial |
| A-Q12 | job creation/persistence есть, polling/retry paragraph не доставлен — partial |
| A-Q14 | bounded cancel/poll и отсутствие unbounded resubmit; точное правило повторной identical recovery action не доказано — partial |
| A-Q25 | false flags допускают host explanation supported snippets; нет edit permission — достаточно для вопроса |
| A-Q26 | retrieval/facet fields различены; нельзя из этого выводить semantic completeness — partial packet |
| B-Q11 | текущие job/cancel routes и bounded polling есть; весь preparation-success/original-retry sequence не доставлен — partial |
| B-Q12 | acknowledgement не terminal; bounded terminal inspection — достаточно |
| B-Q14 | CLI budget/context pack, не full MCP metadata accounting — недостаточно |
| B-Q25 | insufficient_evidence |
| B-Q26 | indexing/chunking сведения без inactive-generation ranking invariant — недостаточно |

Все фактические packets сохранены без переписывания. Данный fixture не весь production corpus и не resource-matched before/after benchmark. Не заявляются рост recall, correctness негенерированных ответов или независимый success gate. Search/scorer/budgets/flags/defaults/dependencies не менялись. Remaining delivery/recall gaps не исправлялись подгонкой документации.

После шага остановка; шаг 04 не начат. Открытые ограничения предыдущих шагов остаются открытыми.

Эта остановка относится к исходному выполнению шага 03. По следующему запросу пользователя выполнен шаг 04; при последующем ревью шага 03 удалено оставшееся `only covered claims`, уточнены lanes `docs_answer` и усилен regression assertion. Финальные после ревью packets сохранены отдельно в [review-controls](review-controls/provenance.json), без перезаписи предыдущих прогонов; corpus hashes соответствуют коммитуемым страницам. Объединённая перепроверка — [81 passed](review-tests.log).
