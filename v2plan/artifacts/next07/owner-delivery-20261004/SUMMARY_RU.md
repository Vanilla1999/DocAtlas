# Owner delivery: реализовано, review выполнено, native run завершён без N10

## Итог

**Интегрированная попытка REJECTED: transport нарушает целостность цитат после handler validator.**
Это содержательный отказ, не ошибка wiring и не незавершённый запуск.
Отказы hidden_structural_dependency устранены на измеренном корпусе; принимать
весь candidate по этому факту нельзя. Код после meaningful результата не менялся.
N10: EXCLUDED_BY_USER / NOT_RUN; исторический REJECTED не переименован.
Rollout: NOT_AUTHORIZED.

## Последовательность и evidence

- Baseline: ea7eef380eb2b0a11b0216063939b2b8ae1773de, run 37231552540.
- 8caf15ae: закрытые технические обязанности и протокол до реализации.
- 5f982a56: source-owner helper, producer/consumer mapping и tests.
- 4dfd4e75: авторский review до исполнения; не внешний независимый аудит.
- Первый запуск f0edb888 / 37232816139: 172 PASS, 1 invalid development-test
  precondition. Подготовленный текст помещался в один search chunk, assertion
  нескольких chunks сработал до вызова проверяемого proposals. Target/corpus
  SKIPPED. Этот run и поправка сохранены в REVIEW_AMENDMENT_RU.md.
- 79534699f8221448a5e4a8f8432568046040219d: только размер test fixture и hash
  workflow исправлены; algorithm byte-identical проверенному 5f982a56.
- Настоящий run [37233045584](https://github.com/Vanilla1999/DocAtlas/actions/runs/37233045584).
- Artifact ID 11314577329, имя next07-owner-delivery-79534699f8221448a5e4a8f8432568046040219d.
- SHA-256 ZIP: 96777481bdde68a8d7b6cff505bcb256d6a018708e8ca1bdb09402e7589b0f4d.

В ZIP: tests.xml/tests.log, target/{0,1,partial}/{N,C,trace}.json,
corpus-replay/cases/<id>/{N,C}/{capture,assessment}.json, per-case result.json,
corpus-replay/result.json, protocol, postflight-hashes, pip-freeze и summary.json.
Actions success означает завершение команд, не отсутствие quality/audit failures.

## Правка

После прежнего FTS/BM25 порядка исходный search hit преобразуется в точный
непрерывный диапазон всех пересекаемых parser-owned секций. Оригинальные
retrieval_span/content и score/order сохранены. Затем тот же штатный путь заново
проверяет snapshot/current catalog/hash/lifecycle/read admission.
Consumer вычисляет допустимый delivery span из raw snapshot, а не доверяет
metadata флагу. Старый dependency guard и exact/subject/state guards сохранены.
Нет новых IO, guessed parent, parser смысла, threshold, corpus-specific exception
или post-rejection rescue.

Не изменены docmancer, eval, tests, third-party ports, scope wiring и first_fit.
В existing candidate изменены только импорт, post-ranking materialization и
проверка canonical delivery spans. Freeze этих границ проверен workflow.

## Измеренные результаты

**173 PASS** в полном project environment, включая реальные source-preparation,
source guard mutations, длинный owner с поздним restriction и public MCP packet.

| Native target | Доставка | Whole-DTO tokens / sources |
|---|---|---:|
| P1 | 17 seconds + LeaseExpired, owner и expiration сохранены | 611 / 3 |
| P2 | 29 seconds + WaitExpired, owner и expiration сохранены | 601 / 3 |
| P3 | 17 seconds, exception не выдумана | 439 / 2 |

Target validator и source audit чистые. Flags False.
Корпус: 80/80 пар исполнены и оценены, 80 N + 80 C public calls,
frozen inputs неизменны. Это НЕ означает, что все packets прошли source audit.

| Метрика | До | После |
|---|---:|---:|
| Fresh assessor retained vs same-run N | 23 | 46 |
| Fresh recognized losses vs same-run N | 27 | 3 |
| Fresh gained vs same-run N | 3 | 6 |
| Historical49 retained, audit-clean | 22 | 40 |
| Historical49 definite lost | 15 | 0 |
| Historical49 UNKNOWN | 12 | 9 |
| C cases с source audit errors | 0 | 17 |

Новый C имеет 52 recognized claim IDs против прежних 26: recognized потерь
прежнего C нет, additions 26. Однако 5 прежних C IDs теперь находятся в packets
с audit error, поэтому это НЕ сертификат сохранения их provenance. Fresh
retained с чистым source audit обеих сторон только 40; clean C supported всего44.

В unchanged N между двумя runs изменился assessor outcome ruff-05: supported
стал нераспознанным. Причина не установлена. Не выдавать всю разницу таблицы за
чистую причинную оценку одного patch; основное сравнение N/C — внутри нового run.

## Что осталось в трёх recognized losses

- fastapi-02: supporting row [1095,1610] background-tasks.md отвергнут
  missing_visible_exact_or_subject. Этот guard не удалялся и не ослаблялся.
- ruff-06: обе supporting rows [6810,9532] и [0,9532] configuration.md были
  allowed и selected; source повредился позже при transport compaction.
- uv-05: supporting row [6330,9344] pip/compatibility.md была allowed и selected;
  после этого transport обрезал её.

Во всех C decisions нет hidden_structural_dependency; остаются157 отказов
missing_visible_exact_or_subject по строкам всего корпуса. Это не число lost IDs.

## Точный новый blocker: compaction после проверки

В 17 C packets original JSON превысил32 000 bytes. Уже ПОСЛЕ чистого handler
validator вызывается compact_mcp_payload. Он рекурсивно сокращает strings до
900 chars и lists до8, добавляя текст `… [truncated ... chars]` в исходные цитаты.
Суммарно115 snippets отличаются от их validated snapshot. N audit чистый.

Код, проверенный на actual run commit79534699:
- docmancer/mcp/_docs_server_part01.py::call_docs_tool_payload в конце вызывает
  compact_mcp_payload(payload, tool=name) после handler.
- Тот же файл::_mcp_tool_result дополнительно вызывает compactor при формировании
  SDK/stdio result. Следующая правка должна учитывать обе реальные границы.
- docmancer/docs/interfaces/mcp/output_contract.py: DEFAULT_MCP_COMPACT_OUTPUT_MAX_BYTES=32000;
  compact_mcp_payload вызывает _compact_value(text_limit=900, list_limit=8).

Пример pydantic-01: original35759 bytes,12 selected sources →8 final sources,
8 изменённых цитат; handler_validation.errors=[] до compaction. Независимый audit
правильно ловит несовпадение snippet/snapshot и нарушение точного диапазона.
Это не старый false positive на LF/CRLF и не неизвестная применимость.

Повреждённые cases:
pydantic-01,07,08,10; ruff-01,03,04,05,06,07,08,09,10; uv-02,05,08,09.
Final public median3240.5 tokens, max8850, max17 sources — ПОСЛЕ compaction;
эти числа не описывают необрезанную materialized выдачу.

## Конечная граница этой работы

Механизм owner materialization работает в измеренных tests и больше не является
массовым veto. Но predeclared OWNER_DELIVERY_VALIDATED требовал чистого final audit,
поэтому общий verdict REJECTED_SOURCE_INTEGRITY. Не объявлять DONE из-за зелёного CI.
N10 не запускался, не исправлялся и не исключался из старых результатов задним числом.
Historical partial ledger, полная классификация лишнего context, full product
suite и rollout в этой работе NOT_RUN.

Следующая отдельная ответственность: serializer/transport не может изменять
validated source bytes. При настоящем ресурсном отказе должен быть корректный
отказ, не усечённая цитата с прежними hash/lines. Исполнение caller-owned read
policy требуется до терминальной выдачи, а integrity проверка должна относиться
к реально сериализованному packet. Не повышать32000 до произвольного числа,
не отфильтровывать audit errors и не менять ranking/parser под этот дефект.
Transport code в текущей замороженной попытке НЕ менялся.
