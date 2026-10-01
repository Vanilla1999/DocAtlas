# Шаг 06 — bilingual recall: диагностический стоп, без активации

После коммита шага 05 `dc71516a` выполнена начальная двух-lane диагностика шага 06. Это частичный результат, не полностью пройденный acceptance gate. Диагностика и [саморевью](REVIEW_RU.md) включены в отдельный коммит по запросу пользователя; без push/merge. Следующий запрос разрешает начало шага 07.

## Baseline и invariants

- Installed **main** `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c`, версия/import path и все Python runtime hashes — [provenance](experiment/provenance.json). Проверено byte-for-byte соответствие установленного пакета этому локальному main, не текущей continuation ветке. Fetch/new upstream main не выполнялся.
- Git archive этого main materialized в новый isolated fixture: **134 catalog documents**, SHA256 каждого сохранён. Никаких правок корпусу между lanes, добавленных gold paragraphs, новых aliases или новых defaults. Archived audit не подключён как operational corpus.
- Только `question-only` и `same-need-lookup` через существующий public `lookup_queries`, lexical/offline, один stdio MCP process. [Protocol](experiment/protocol.json) сохранён до requests.
- Original Q07/Q14/Q29/Q30 projectA questions из audit не менялись; scope/project identity одинаковые. RU Q07/Q29 используют те же same-meaning EN translations, что уже были открыто задекларированы в translation10. EN Q14/Q30 — duplicate-original controls, **не** новый answer-oriented paraphrase. Вопросы не содержат version/comparison literals для отдельной bilingual preservation проверки; general version/negation/comparison acceptance не заявляется.
- [Runner](run_experiment.py) сохраняет official stdio wires. Отдельный повторный diagnostic observer использует тот же installed-main/index/requests и сохраняет `*-trace.json.gz`, включая pre/post-cap windows; это **другие calls**, не instrumentation самого stdio вызова и не его latency. Финальные source path/snippet signatures Q29/Q30 сверены с wires.

## Red baseline → same-need lookup, конкретные facts

[Fact assessor](assess_diagnostic.py), [диагноз и фактические witnesses](experiment/fact-diagnosis.json). Сопоставляется verbatim paragraph fact на фиксированном source path, а не заголовок или одно совпадение README identifier.

| Case/lane | Pre-cap | Post-cap | Query window | Qualified fragments | Final packet |
|---|---|---|---|---|---|
| Q29 original RU | нет policy fact | нет | нет | нет | нет |
| Q29 + EN same need | **есть exact policy fact** | **есть** | **есть** | нет | нет |
| Q30 original EN | нет isolation fact | нет | нет | нет | нет |
| Q30 + duplicate EN lookup | нет | нет | нет | нет | нет |

Q29 witness: `docs/security/mcp-runtime-threat-model.md` — `Ordinary repository Markdown is cited data.` с окружающим scoped-agent-policy и cannot-override контекстом. Lookup действительно восстанавливает этот факт раньше, но **его нет в qualified fragments и final packet**. Эта граница включает application candidate eligibility/order + qualification; нельзя приписывать loss одному qualification predicate без дополнительной instrumentation. Передать диагноз в шаг 07, не расширять multilingual pipeline.

Q30 witness в corpus существует: `wiki/Architecture.md`, отдельные SQLite/extracted states per project identity и невозможность satisfy another repository's query. В обеих lanes отсутствует уже pre-cap. Duplicate EN lookup не является новым bilingual recall lever; Q30 не доказан исправленным. Обе финальные выдачи — PyPI release checklist, не isolation fact.

## Other early controls и useful evidence/noise

- Q07 RU: original пустой; lookup даёт CLI commands (init/install/fetch). Availability выросла, но целиком requested candidate/ignored discovery contract не доставлен; не считать full fact recall gain.
- Q14 EN: source signatures и смысл не меняются; generic prepare workflow вместо точного stop-on-repeated-recovery rule. Duplicate-original control не даёт gain.
- Q29: original возвращает два docs-index blocks, lookup — один evaluation/research index block. Policy usefulness по-прежнему 0, хотя pre-cap recall вырос. Не считать fewer irrelevant blocks успехом.
- Q30: две checklist citations в обеих lanes; useful isolation evidence 0.
- Во всех Q29/Q30 packets false answer/edit certification сохранена; source URI generation не использована как ranking/citation успех.

## Почему остановились, что НЕ выполнено

Пункт 17 шага 06 запрещает расширять retrieval ради уже найденного факта; для Q29 такая downstream потеря подтверждена. Первоначально это правило применено слишком широко: оно само по себе не требует прекращения всех остальных диагностических controls. Новый перевод/rewrite Q30, Typer05 и расширенный distractor/unsafe/wrong-version/stale/private-config/unsupported-guarantee matrix **не запускались** и остаются открытыми. Это не успешно завершённый эксперимент и не safety gate. Не заявляются полная проверка guards, general bilingual retention или независимый успех. Production guards не менялись; активация не разрешена.

[2 diagnostic tests passed](diagnostic-tests.log): exact original question/request identity/scope, lookup-only difference, README/ignore-previous-instructions intent без expected answer injection, no activation и реальный downstream loss вместо final success. Red — baseline fact miss в сохранённых question-only wires/traces; tests фиксируют итог диагностического сравнения, не реализацию нового retrieval механизма.

Scorer после шага 05 одинаковый для обеих lanes; qualification/caps/packing/budgets не менялись. Saved-pool packing replay не проводился и не выдан за retrieval gain. Результат: **не активировать**; Q29 downstream diagnosis передан для отдельного шага 07, Q30 pre-cap miss остаётся открытым. После этого диагностического стопа остановка.
