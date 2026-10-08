# PR #211: согласованная отмена фиксированного catalog ceiling

Дата: 2026-10-08. Отчёт автора для независимого review.

## Решение владельца и граница изменения

В продолжении этой сессии владелец отменил фиксированный catalog limit 6144 bytes
и попросил стремиться к минимуму. Это новое указание заменяет прежнее сохранение
catalog ceilings в пункте 3 CURRENT_WAVE_DECISIONS_RU.md. Для default tools/list
не устанавливается ни 6144, ни прежний hard ceiling 10 KiB, ни предложенный 7168,
ни другое произвольное число.

Изменение **является согласованной сменой acceptance policy**. Оно не является
исправлением runtime failure и не доказывает дополнительную экономию bytes.
Catalog по-прежнему должен быть компактным, самодостаточным и измеримым. Сохранены
три обычных tools, advertised input/output contract, discoverability, scope/source/
version bindings, consent, validation и existing advanced boundary. Отдельный
действующий output schema gate **<1000 bytes** остаётся.

Policy не отменяет acquisition/search/work/read bounds, retrieval gold/thresholds,
другие CI/downstream gates или реальные client checks. Deferred retrieval не
меняется. Workflows, production code и четыре Python files предыдущего frozen
prose slice не изменены этим policy slice.

## Изменённые пути

1. `tests/docs/test_mcp_token_footprint.py`: изменён только body существующего
   `test_default_public_catalog_meets_task35_hard_and_target_budgets`.
   Его историческое имя оставлено для сохранения test inventory и явно объяснено
   комментарием. Восемь test nodes модуля, decorators, imports и все прочие bodies
   неизменны.
2. `v2plan/CURRENT_WAVE_DECISIONS_RU.md`: пункт 3 явно ссылается на новое решение;
   добавлена датированная политика минимизации/измерения без fixed catalog gate.
   Пункт 2 о deferred retrieval остаётся прежним.
3. `roadmap/35_STRUCTURED_TRANSPORT_AND_COMPACT_MCP_SURFACE.md`: исправлены только
   catalog budget section и связанные required-work/acceptance bullets. Отмечено
   retirement прежних 6/10 KiB; остальные Task 35 требования не переписывались.
4. Настоящий отчёт. Исторические checkpoint, golden fixtures и старые acceptance
   manifests сохранены. Их прежний статус 6144/7168 относится к прежнему решению.

## Прежний gate и его содержательный successor

Поиск в tests/scripts/.github/measurement code обнаружил один active default
catalog gate: указанный terminal test node. Из него удалены:

```python
assert report["mcp_tools_list_bytes"] <= 6 * 1024
assert validate_footprint_report(report, max_tools_list_bytes=10 * 1024) == []
```

Вместо числового catalog отказа node проверяет:

- Actual default tools в точном protocol порядке: get_docs_context, prepare_docs,
  docs_status. Три unique attribution rows соответствуют этим трём tools.
- Report total равен canonical UTF-8 serialization actual tools/list.
- Каждый per-tool total, input schema, output schema и description размер равен
  размеру соответствующего actual component, а не stale measurement/estimate.
- Сумма tool totals плюс JSON array framing равна catalog total. Output schema
  уже внутри tool total и не прибавляется второй раз.
- Сохраняется общий validator report: schema version, tool count, bounded report,
  bounded attribution и отсутствие duplicate payload в representative fixtures.
- У normal get_docs_context ровно семь selection fields, без context_format;
  output остаётся object с required status и без default oneOf/patch branch.
- Advanced mode по существующей конфигурации advertises context_format с точными
  patch_context/null values; его первая output branch равна normal output.
  Normal output меньше full advanced output, а его прежний gate <1000 сохраняется.

Schema equivalence с независимой frozen базой, 417 boundary cases, negative
dispatcher-before-I/O controls и meaning-level guidance проверяются прежними
соседними tests. Этот policy slice не удаляет и не подменяет их проверкой размера.
Здесь нет vacuous `length >0`, нового magic ceiling, skip/xfail или удаления nodes.

## Почему optional CLI limit остался

`validate_footprint_report` уже имеет default `max_tools_list_bytes=None`.
Measurement CLI `--max-tools-list-bytes` — optional, явно задаваемая вызывающим
локальная диагностическая граница. Production measurement API не требовал правки.
Неизменный `test_report_validation_enforces_explicit_local_gates` по-прежнему
проверяет, что явно заданный caller limit реально применяется. Это не скрытый
repository-default catalog ceiling и не merge requirement.

Поиск не нашёл других active 6144/10 KiB catalog gates в tests/scripts/.github.
Исторические measurements в reports не являются исполняемыми gates и не менялись.

## Текущие measurements

Policy сама bytes не меняет. Включённый отдельно frozen prose slice даёт:

| Компонент | Catalog/tool bytes | Input | Output | Tool description |
|---|---:|---:|---:|---:|
| Catalog | **6918** | — | уже включён | — |
| get_docs_context | 2342 | 490 | **860** | 917 |
| prepare_docs | 3950 | 3600 | 0 | 295 |
| docs_status | 622 | 415 | 0 | 153 |

Полная сумма: `2342 +3950 +622 +4 =6918`; 4 bytes — brackets/commas списка.
Canonical catalog SHA256:
`10160389f0052bc464c6af49b67187d48baa6e0e99f27bdbdfbff559740aa9af`.
По отношению к 7066 после предыдущей волны уменьшение составляет 148 bytes,
к независимому 21fe catalog 7602 — 684 bytes. Это результат prose slice, не policy.
Measurements не являются реальными model tokens или certification клиента.

## Локальная проверка и предел evidence

Без импорта DocAtlas package, provider/client calls и сторонних dependencies:

- AST сравнение доказывает прежние 8 node IDs и неизменность всех остальных nodes
  в measurement test module.
- Из actual PUBLIC_ADVERTISED constants получен canonical catalog. Неизменный
  `mcp_footprint.py` исполнен из файла как stdlib-only measurement module;
  lazy CLI main/server import не вызывался. Report даёт таблицу выше и проходит
  validator без caller limit; явно заданный `max_tools_list_bytes=1` отвергается.
- Normal measurement/default-contract prefix нового test body исполнен из AST
  с actual literal catalog. Намеренно повреждённые catalog total, row input bytes,
  row output bytes и row description bytes каждый отвергаются этим же prefix.
  Advanced assertions требуют настоящего normal CI; они локально не запускались.
- Python AST parse и `git diff --check` проходят. Поиск подтверждает отсутствие
  active default catalog numeric assertions после изменения.

**Pytest/MCP/installed/client PASS этим отчётом не заявляется.** Полный node,
его normal/advanced producers и соседние contract tests должны пройти обычный
совместный CI после интеграции. Переход старого footprint node из FAIL в PASS
следует учитывать как approved policy migration, а не runtime bug fix.

## Frozen hashes для независимого review

| Файл | SHA256 |
|---|---|
| `tests/docs/test_mcp_token_footprint.py` | `9492eef60963011161b43da2f9c8c06d2d22c8c1aa574fefd05e7a997f6c94a7` |
| `v2plan/CURRENT_WAVE_DECISIONS_RU.md` | `7fa62f6b4aebc6fa922bf4b6ae35ccc94d10627b62bd54cd5aa01a3e07c11411` |
| `roadmap/35_STRUCTURED_TRANSPORT_AND_COMPACT_MCP_SURFACE.md` | `09b619fbfbd38d61720af0fb578b278344f742f556427603b5e6446b9cb2416e` |

Это hashes файлов, не tested SHA. Изменения готовы для independent review;
никаких remote writes автор не выполнял.
