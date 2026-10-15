# PR #211 — текущая P1 closure

## Цель и граница

Агрегат P1 больше не принимает исторические зелёные P1.4–P1.6 за
доказательство текущего runtime. Новый протокол:
`p1-agent-truth-current-closure-v2`.

Он проверяет три отчёта из конкретного checkout:

| Slice | Текущий протокол | Независимая проверка | Условие quality PASS |
|---|---|---|---|
| P1.4 | paraphrase-retrieval-report-v2 | paraphrase_robustness.verify_report | исходные 14/14 cases, без runtime error |
| P1.5 | mixed-evidence-provenance-retrieval-v2 | mixed_provenance.verify_report | исходные 7/7 cases, без runtime error |
| P1.6 | evidence-is-data-public-delivery-report-v2 | evidence_is_data.verify_report | исходные 6/6 cases, полный полезный факт и все delivery/authority guards |

Ни один frozen вопрос, факт, candidate, отрицательный контроль, scorer или
quality threshold этим slice не меняется. P1.4/P1.5 проверяют реальные
fixture reads; P1.6 использует frozen candidates на retrieval boundary,
реальный public handler и установленный MCP serializer. Closure не объявляет
indexed retrieval для P1.6, stdio/client delivery, LLM-поведение, autonomous
Agent Truth либо готовность Stable доказанными.

## Как связывается evidence

Каждый current report обязан указывать настоящий `git rev-parse HEAD` этого
checkout; PR workflow использует свой фактический merge checkout. P1.6 получает
только отсутствовавшее поле `code_commit` и его проверку. Общая функция чтения
HEAD использует тот же Git-вызов, который уже применяют current P1.4/P1.5;
closure переиспользует её. Новых зависимостей нет.

Собственные verifiers P1.4/P1.5/P1.6 заново проверяют original roster, hash/range
bindings, frozen input, каждый case check, summary и runtime manifests.
P1.6 сохраняет свой отдельный proof-runtime manifest и source identities
recovery/adversarial/mutation gates. Импортированные исходники каждого
процесса сверяются с текущими файлами, а общие пути в трёх manifests должны
иметь одинаковые SHA256. Разные полные наборы imports допустимы: public
delivery и indexed fixture reads импортируют разные модули.

В closure сохраняются hash каждого входного JSON, полный исходный summary,
family summary P1.4 и все проверенные case checks. Raw hostile body в агрегат
не копируется; ошибки представлены stage/type/hash. Подробные причины
остаются в исходных current reports и их runner logs.

Проверка целостности и итог качества разделены. Корректно записанный
отрицательный результат проходит integrity verification, но оставляет
quality и общий verdict FAIL. `verify_closure` заново выводит ожидаемый
агрегат из переданных файлов и outcomes; изменённые или скрытые поля не
принимаются даже при уже отрицательном baseline.

## Historical guards сохранены

Старые assertions `_assert_input_evidence` сохранены дословно для архивных
P1.2–P1.6. Это обязательный archive guard, а не замена current quality.
Сохраняются все пять source identities и семь обязательных путей installed
harness. Наличие этих исходников теперь называется наличием harness, без
прежнего вывода `installed_transport_contract_green=True`.

P1.1–P1.3 явно помечены HISTORICAL_CONTEXT; проверки task count 11,
false-supported/contamination 0, ablation no-change, отсутствие неподтверждённых
изменений public API, replay boundary и запрет автоматического autonomous
promotion остаются. Все committed historical JSON, включая старую closure,
остаются неизменны. Отдельные required CI и installed/client acceptance
по-прежнему необходимы на конечном SHA.

## Workflow и сохранение failures

В одном checkout выполняются исходные first-divergence/ablation guards,
current P1.4/P1.5/P1.6 quality runners и их oracle controls, прежние Agent
Developer adversarial и adversarial-mutation gates, syntax/diff/temp-workflow
guards. Следующие независимые шаги выполняются и после предыдущего FAIL.

Workflow записывает реальные `steps.*.outcome`, GitHub SHA, run ID и attempt
в отдельный receipt. Closure требует ровно 12 известных outcomes, корректный
checkout binding и success каждого. Missing, skipped, cancelled, failure,
неизвестное значение, malformed outcome либо receipt другого SHA дают FAIL.
Closure и её четыре oracle controls остаются отдельными обязательными шагами.

Runner всегда сохраняет новый `p1-agent-truth-closure.current.json` либо
явно заданный temporary output до итогового verdict; запись поверх history,
входных отчётов или outcome receipt запрещена. Workflow всегда загружает
три current reports, receipt и closure artifact, в том числе при ошибках.

## Совместимость существующих callers

На a348cafb основной CI advanced-contract не вызывает closure. Старый
P1-stack advanced loop вызывает P1 scripts без аргументов и останавливается
на первом FAIL. Default input paths closure переиспользуют DEFAULT_OUTPUT
трёх текущих runners: P1.4/P1.5 в RUNNER_TEMP, P1.6 в results с суффиксом
.current.json. Архивные v1 defaults не используются.

Вызов без --gates явно сохраняет FAIL из-за отсутствующего актуального
workflow receipt. Self-controls проверяют наличие пригодных current inputs
до mutations и возвращают явный FAIL/1 вместо None/TypeError. P1-stack loop
для успешной closure потребует отдельного подключения реальных outcomes;
этот slice не подделывает receipt и не меняет данный caller.

## Контроли и фактические результаты

Сохранены четыре исходных self-test names. Они используют уже собранные
workflow reports, не повторяют indexing/HTTP/project preparation.
Fault injections проверяют forged PASS поверх честного FAIL, скрытые summaries
и case checks, v1-подмену, чужой SHA, self-consistent подделку runtime manifest,
отсутствующий вход, отсутствующий/пропущенный/ошибочный/malformed gate,
receipt другого checkout, потерянную строку scorecard, overclaim и private path.
Каждый mutation требует здорового соответствующего baseline guard; проверка
ведётся в integrity mode, поэтому прежний quality FAIL не считается убийством
мутанта.

Исходная точка review — public a348cafb4807a5b4af852e0029cf6b98ff7a3f91.
Новый P1.6 public-delivery runner фактически прошёл 6/6, полный факт 1/1,
runtime errors 0; oracle controls 6/6 и integrity PASS в run 37998331760,
job 114049949409, merge checkout 0e84988d21bb06a86c14714e077098e5cf0cb5d9.
Этот workflow в целом FAIL: сохранённый adversarial gate дал 24/28,
а mutation gate отказал из-за неуспешного baseline. Это не current closure PASS.

Сам closure slice прошёл только статическое чтение исходников и сверку
manifest/roster. Runtime, syntax и четыре controls должны быть подтверждены
новым совместным CI после review и публикации; локального выполнения не было.
