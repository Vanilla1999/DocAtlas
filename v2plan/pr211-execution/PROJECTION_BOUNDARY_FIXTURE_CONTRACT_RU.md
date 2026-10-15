# PR211: три projection fixtures по текущему контракту

## Основание и граница

Исходный runtime: PR HEAD `80c8fbbb3e8c379467a9075f93f7165d080f8432`,
checkout merge `f04b42774b00dadbca48ca579ca9ea234442b750`.
Дерево обоих `a838749f57ff0165ab925590656f64e0799a2e05`.
[JUnit reader 114077935805](https://github.com/Vanilla1999/DocAtlas/actions/runs/38006157209/job/114077935805)
показывает для `tests/docs/test_context_projection_boundaries.py` 14 PASS / 6 FAIL /
0 ERROR / 0 SKIP. В полном core каждого Python: 6057 PASS / 1680 FAIL / 0 ERROR / 10 SKIP;
это не полный успешный CI.

База изменения: `f7b9253c8e477babf276ae8dd2cb18905451cd15`.
Blob модуля по-прежнему `8a4151b586f0f14405b363feaacfbbb1d69e47b7`.
Меняются только тела трёх существующих tests и аргумент `tmp_path` первого.
16 test names / 20 expanded cases, обе parameter lists, fixture/helper/import
source вне этих тел, остальные 13 tests и три frozen quality inputs сохранены.
Ничего не удаляется и не помечается skip/xfail.

## Разбор всех шести отказов

| Сценарий | Доказанная причина / оставшийся вопрос | Изменение и сохраняемый guard |
|---|---|---|
| Path-only / ALPHA_KEY | В ручном plan у original отсутствует `relation=direct`; synthetic `query-path-1` / `exact_path` вообще не является авторитетным публичным query. Один путь не доказывает topic в body. | Настоящий finite member capture того же вопроса и того же body. Hash/path/project/catalog/span подтверждены producer; полезный literal context не получает original или path query credit. Filename-only, heading-only, identifier-prefix и wrong-path transformations проходят собственный native capture и должны безопасно отказать. |
| Strong explicit lookup vs generated alias | Original и host lookup не имеют обязательных relation. После текущего typed plan реальные body matches различаются: strong 3/4, weak 2/4. `_facet_aware_candidates` использует qualified required match ratio; synthetic alias не должен давать rank/credit. | Тот же original и тот же explicit lookup через `build_documentation_query_plan`; old generated alias и incoming weak alias trace оставлены как отрицательный input. Strong-first, целый body, реальный lookup credit, отсутствие original/alias credit и validator сохранены. |
| Complete variant vs prefix | Нет `_independent_query_plan`, поэтому requalification отвергает inherited `qualified=True`. Одного plan недостаточно: natural lookup буквально совпадает только по derived/files/configuration (3/8). `clearing/clear`, `preserve/preserving`, `source/sources` не являются literal matches. | Полный original natural question и весь raw passage неизменны. Добавлен явно заданный автором fixture lookup `` `clear-index` ``, который реально квалифицируется. Old query-lookup-2 prequalified trace сохранён как отрицательная примесь. Первый variant обязан сохранить конец restriction; полный raw passage с apply condition остаётся eligible alternative; original остаётся unqualified, old synthetic trace не переносится. |
| Frozen cache reset | Оба evaluator witness отсутствуют в final payload; сами preview/preserve facts есть в active `docs/index-cleanup.md`. JUnit не показывает точный retrieval/qualification/selection этап потери. | Тест, исходный вопрос, оба lookup и gold не меняются. Нужны отдельные same-call stage records уже вычисленного V2 report. |
| Frozen architecture boundary | Final payload содержит только `docs/PROJECT_MAP.md`; infrastructure witness в module doc отсутствует. Факт физически присутствует и module doc включён в active catalog. `scope=all` в service снимает doc_scope filter; это не основание выкинуть module obligation. | Все четыре obligations и исходные inputs остаются. Нужен точный stage receipt, прежде чем менять retrieval/selection. |
| Frozen request flow | Final payload не содержит `sources`; четыре требуемых факта есть в `docs/modules/project-context-retrieval.md`. Из одного KeyError нельзя заключить, что это правильное abstention или устаревшая эвристика. | Frozen question, три host lookups, source witness, no-answer/no-edit и false-coverage guards сохраняются. Stage diagnostics отдельно. |

## Точный текущий контракт

- `docmancer/docs/domain/documentation_query_plan.py`
  `0cd20b1138f1a3a2740729677d9588414f2dcf32`: original/direct,
  explicit host_lookup/host_lookup; explicit path — scope metadata, не дополнительный query.
- `docmancer/docs/application/context_query_probes.py`
  `79bfec078a8a37a8408df22f8a750d65ddb95550`: `authoritative_queries`
  требует полный original identity и разрешает только original и пять explicit lookup IDs.
- `docmancer/docs/application/_docs_context_projection_core.py`
  `15cc1f04b03fd3d0ccf83099f1f4ee09b87844c2`: фильтрация plan и повторная
  квалификация текущих видимых bytes; старый incoming qualified flag не даёт полномочий.
- `docmancer/docs/domain/literal_context_admission.py`
  `0dc5fb950bd3d4a5893e195baefb01897e3aa525`: current immutable member,
  catalog/hash/scope/occurrence checks; только body context с `coverage_credit=False`.
- `docmancer/docs/domain/technical_tokens.py`
  `bea6c48c02760cbb2e897c7cc6ab5f46b7a51fb5`: non-exact retrieval тоже
  требует literal spelling, без inflection.
- `docmancer/docs/application/context_candidate_ranking.py`
  `c04a10e3c18b4d8eed9b64b5fdd266b8ed0056f7`: qualified explicit required
  match ratio сохраняет meaningful ordering guard.
- `docmancer/docs/application/context_variant_retention.py`
  `b328b2869324fb2b304e819b02bd3d3b5898d842`: варианты повторно квалифицируются,
  complete source span выигрывает у незавершённого prefix при одинаковом coverage.
- `tests/docs/_reference_binding_fixtures.py` `7fd30e607488b9841e3fd78f146af737c6c1c04e`,
  `tests/docs/_global_evidence_fixtures.py` `ce01e23f813c876921be2995f2ce19e906e3c27d`,
  `eval/evidence_quality_v2/runtime.py` `73e5e30fe41394d2be33271a03d9e550bf6f4ae1`:
  неизменный real public member setup с finite catalog и explicit prepare grant,
  unpatched public call, без замены qualification.
- `eval/project_context_quality/capture_public_context.py`
  `9ebe12c94fb65dbf9767251fe3f509fd186b1da1`: наблюдает реальный projector и возвращает
  тот же результат, замороженный для test assertions.

В path fixture прежняя неаттестованная `line_start=11` заменена настоящими coordinates
однострочного fixture file (1, 1); исходный body не дополнен и не переписан.
Этот существующий test теперь делает один positive и четыре independent negative
fixture captures. Они изолированы и заранее задают bytes/finite membership;
пустой handler exception не считается отрицательным успехом.

В variant unit fixture сохраняются прежние явные candidate policy fields;
меняется источник query authority. Это проверка qualification/variant ordering
на переданном unit candidate, не утверждение об installed или native MCP delivery.
Текущий context_windows.py (29c5bc796eb31793b4bcc973c30209a86445893c) считает
законченную sentence допустимой границей: первым может идти её более короткий
полный span. Тест сохраняет старый guard против mid-sentence prefix и дополнительно
требует сохранения всего raw passage среди eligible alternatives, не приписывая
первой sentence невидимую apply condition.
Frozen cache reset по прежнему natural lookup остаётся самостоятельной quality обязанностью.

## Проверка и дальнейший gate

Pure text inverse трёх замен восстанавливает исходный blob побайтно.
Никакой Python/AST/import/pytest/local runtime при подготовке не исполнялся.

- Старый module SHA-256: `9429fc523e58fbe7c15c727a9e6548ad96de6e006cc354a7492a6adae67a9a3a`.
- Новый module SHA-256: `a769034a890618a4783b5e9b431246675ecce6663059d4067150a6b07fe745e2`.
- Упорядоченный JSON roster 16 names SHA-256: `bb887ebd248d68d98a74c6adeb876e1f25709f9d3d0beb88832a631c4f8745e4`.
- Ordinary collection остаётся 20 cases; диагностическая registration не меняется.

Независимый static review contracts и root: APPROVE для code blob
`da596b3c19c73a21788b4871e2564d622dfd7ae7`; оба проверили узкую границу fixtures.
Root актуализировал ссылку на неизменённый в этом slice literal admission исходник. Новый runtime на конечном опубликованном SHA
ещё не выполнен. Даже успешные три fixture migrations не закрывают frozen V2 quality:
их PASS требует настоящих неизменённых witness facts в final visible context.
