# PR211: directed precheck против возврата output caps

Статус: собственные четыре направленные поломки **PENDING**, новый общий baseline **59 cases /35 mutants PENDING**. Этот slice не меняет production и не удаляет старый budget test до подтверждения successor.

Пользователь отменил обязательные output ceilings: schema6144 bytes, evidence800 tokens и фиксированное source fit. Оптимизация размера сохраняет полезные исходные сведения и guards. Входные/work/read/time bounds и явно заданные caller options не отменяются.

## Имеющийся независимый successor

На actual PR head `c2a6682d2438c9217c3bf26938dcd003391dbc75`, merge `642a14289fddd06408400b4ee6cc5480945e7d1a`,
[reader114124354950](https://github.com/Vanilla1999/DocAtlas/actions/runs/38021212993/job/114124354950)
показывает **32/32 PASS** модуля `tests/docs/test_docs_lossless_context_projection.py` отдельно для Python3.11/3.12/3.13.
В каждом JUNIT_TRACKED record явно перечислены три list/table/code cases
`test_four_distinct_qualified_lanes_survive_without_source_fit_gate`
и `test_context_budget_uses_explicit_optional_output_limits`, все PASS.
Это свидетельство до добавления mutations, не собственный результат данного precheck.

В existing lossless test:
- Четыре авторские query directions имеют собственные источники с 70 различными literal facts на источник.
- Проверяются полные тела, точный хвост, spans, source hash/snapshot, query coverage и false answer/edit.
- Отдельный короткий положительный контроль выполняется до большого примера.
- API control требует отсутствия неявных default caps и сохраняет проверки явно заданных положительных options/invalid zero.

Эти проверки относятся к in-memory core projection. Они не доказывают current-file/catalog acquisition или пользовательский клиент. Настоящая цепочка member→ProjectContext→Unified→MCP проверяется отдельным `PROJECT_READ_PRESENTATION_RU.md`.

Изменение теста — только три именованных сообщения assertion. Новых test functions, parameters, corpus rows или обычных collected cases нет; все остальные source/span/trust guards остаются.

## Faults и ожидаемые kills

| Production fault в изолированной копии | Existing killer | Ожидаемый guard/count |
|---|---|---|
| Default max_sources снова3 | optional output limits API | critical_context_no_default_source_cap;1F |
| Default max_tokens снова800 | тот же API | critical_context_no_default_token_cap;1F |
| Final payload получает только sources[:3] | existing list/table/code | critical_context_full_source_set;3F |
| Уже сформированный payload отклоняется при estimated_tokens>800 | existing list/table/code | critical_context_full_source_set;3F |

Все counts требуют **0 errors/skips**, точного первого assertion message, правильного target roster, одного source anchor, неизменённого oracle и verified mutated import. Ошибка исполнения или сбой раннего короткого positive не засчитывается как kill.

В runner добавлены два existing selectors (1+3 cases), один owning import module `context_budget` и четыре mutants.
Остальные31 mutants и весь execution/validation code побайтно сохранены.
Исходный runner после presentation slice: `7565f0c22d74697224931b321cc1360a8f0799ad`.
Новый runner: `f6ed25aebb6b2df77ac041e2ae6b1dda76bf3b92`, mode100755.
Test base `d2f12bbed978a4efe2fb5ff83718880f8137aa91` → `562ffcda23b8977291f9cfc856a92a5a05ca2bc3`, mode100644.

## Следующее условное сокращение

Устаревший `test_context_budget_is_a_product_invariant` в DQP всё ещё ожидает defaults3/800.
Удалять его можно отдельным узким slice после собственного green baseline и всех четырёх intended kills.
Нужно отдельно обновить versioned crosswalk, точный AST preservation state и owning diagnostic node hash; общий ignore list недопустим.
До этого шага данный precheck не даёт права объявлять retirement или весь required CI успешным.

Исходники обработаны только как текст. Локальных Python/import/AST/pytest/subprocess запусков не было.
Runtime выполняется существующим PR CI без новых jobs/dependencies/providers.
