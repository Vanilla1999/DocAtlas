# QP v4: аудит потребителей на точном tree130 и delta134

Дата: 2026-10-10. Статус: **source audit завершён в объявленном inventory;
retirement не выполнен**. Runtime, Python AST/import и локальные команды не запускались.

## Основание и граница

Проверен commit `0065ce62cacaa31a41e4567717e3c67d602f578b` (130),
tree `628bb7a2eb16f740ce84384925531040f7ec9f5e`.
Git commit и recursive tree прочитаны по точным SHA: 3473 entries,
3005 blob paths, `truncated=false`, gitlinks отсутствуют.

После этого отдельно прочитан полный delta до
`7b56e7b61ff28024349ae13d8e60a591788b83cf` (134),
tree `0efae221bcb7a65e1cf18a3e6525f0f9146c89e0`:
17 изменённых/новых paths, 0 удалений, 0 непрочитанных blobs.
Оба живых QP source blobs остались прежними.

[Машиночитаемый audit](QUESTION_PLAN_V4_CONSUMER_AUDIT_130_134.json)
содержит полный inventory, hashes, строки совпадений, разбор dynamic consumers,
delta134 и точные ranges предлагаемого удаления. Это источник воспроизводимости,
а не свидетельство исполнения pytest.

## Что именно прочитано

| Объект | Количество / результат |
| --- | --- |
| Выбранные current-tree paths | 2213 |
| Различные Git blobs | 2128 |
| Прочитанные UTF-8 bytes | 54373209 |
| Непрочитанные blobs | 0 |
| Blobs с буквальными совпадениями QP names | 13 |
| Отдельно рассмотренные dynamic dispatch sites | 20 |
| Внешние selectors удаляемых функций | 0 в объявленном inventory |
| Внешние прямые imports из двух QP owners | 0 в объявленном inventory |

Выбирались расширения `.py, .pyi, .sh, .yml, .yaml, .toml, .ini, .cfg,
.json, .jsonl, .txt, .dart, .kt, .c, .h, .aidl, .xml`; basenames без точки,
кроме точного regex `^LICENSE(?:$|[.])`; дополнительные `AGENTS.md`,
`SKILL.md`, `CONTRIBUTING.md` и Markdown внутри `.github/`.
Буквальное правило также включает LICENSE-APACHE, LICENSE-MIT и TIKTOKEN_LICENSE.
Полный predicate и исключённые группы записаны в JSON.

Каждый distinct blob получен через GitHub по SHA текущего tree; длина UTF-8
сверена с tree size, вычислен SHA-256. Один read мог покрыть несколько paths
только при одинаковом Git blob SHA. Единственный временный connector error
на AndroidManifest.xml закрыт успешным повторным exact read (172 bytes);
непрочитанных исключений нет.

Поиск — case-sensitive literal substring по полному содержимому: два module
basenames, 26 retirement names и два сохраняемых имени. Для найденных Python
dynamic import/pytest entrypoints отдельно рассмотрены их actual source inputs.
Generic `_rows`/`_unit` из других owners не объявляются QP imports по одному имени.

Не читались 792 остальных paths: главным образом другой Markdown, lockfiles,
архивные logs/patches/diffs и binary/compressed artifacts. Поэтому **отсутствие
ссылок во всём репозитории или во всех возможных runtime-generated строках не
утверждается**. Default-branch search не использовался как доказательство.

## Действующие потребители

| Path | Наблюдение | Действие при будущем retirement |
| --- | --- | --- |
| `.github/workflows/pr174-review-cleanup.yml` | Строка96 выбирает весь `tests/docs/test_question_plan_v4.py`. Workflow checkout относится к его собственной named branch. | Сохранить whole-module selector; два оставшихся tests поддерживают его. Не считать этот workflow запуском PR211. |
| `tests/diagnostic_labels.json` | Behavioral label и hash полного roster28; overrides по удаляемым именам не найдены. | Изменить только один module-node hash после удаления. |
| `tests/conftest.py` | Обязательна согласованность полного module collection. | Не менять. |
| `tests/diagnostic_labels.py` | Hash строится из отсортированных unique base node IDs, соединённых LF без завершающего LF. | Не менять алгоритм. |
| `tests/docs/_question_plan_clause_coverage.py` | Два tests попадают в collection через explicit reexport основного модуля. | Сохранить весь shared source; убрать только его reexport statement из main. |

Оставшиеся совпадения — сами два QP owners и девять historical failure/runtime
records. Исторические records сохраняются; они не являются active selectors.
Отдельного внешнего вызова 26 candidate names или direct import их helpers в
прочитанном inventory не найдено.

Delta131–134 добавляет совпадения только в immutable archives, versioned
crosswalk и его note. Изменённые active product/runner files не добавляют
потребителя удаляемой QP семьи. Новый direct-builder successor выбирает другой,
сохраняемый `test_question_span_coverage.py`.

## Минимальное предложение: 28 collected → 2

Предложение описано, но **не применено**; нового source blob с удалениями нет.

1. В `tests/docs/test_question_plan_v4.py` убрать 24 полных top-level test
   definitions и один explicit reexport statement (physical lines3–6),
   содержащий ещё два tests.
2. Сохранить побайтно остальные imports, helpers `_rows`/`_unit` и два tests:
   `test_code_symbol_aliases_may_widen_retrieval_but_not_proof_shape`,
   `test_code_block_units_preserve_exact_source_spans_for_projection`.
3. Shared underscore module сохранить побайтно. Не добавлять `__test__`,
   skip или waiver collection hook.
4. В `tests/diagnostic_labels.json` обновить ровно
   `module_node_hashes["tests/docs/test_question_plan_v4.py"]`.

| Проверка предложения | SHA-256 / размер |
| --- | --- |
| Исходный main Git blob | `a7cadec822a464a19bf917d69e28e9cc6b0b1496` |
| Исходный main | 45553 bytes /985 physical lines |
| Предложенный main в памяти | 1929 bytes /49 physical lines |
| Предложенный source SHA-256 | `f069eeb98746dabfb0921d711b140581c6528e821e0bb5bb473974f590f6ccb9` |
| Старый roster28 | `ccd2869f6b9bc2c47499fde3ff5efb2fb806dfaa5daa6468e176ea29ad26c8a5` |
| Предложенный roster2 | `346ae9b94978030c282b6b7df4bc553fb05db6189d4b9b684af39c895d049712` |
| Неизменный shared Git blob | `4898e3459e2504cf07f9bacfae8fd6769bdd9c79` |

JSON содержит 25 удаляемых source ranges (24 definitions и один import statement),
их hashes и четыре exact-retained function hashes. Координаты half-open в
декодированном тексте; все code points этого файла BMP, поэтому JS UTF-16
совпадает с Python code-point indices. Это не UTF-8 offsets.

## Какие доказательства ещё нужны

Current precheck crosswalk — `beba5e62b04fe45f6a93986d42b98fb7d0c87bf7`.
Следующий critical target61/39 и 104 individual literal historical/compact child
receipts пока **PENDING**. Этот audit не заменяет здоровый successor, intended
direct-builder kill, full required literal evidence или same-process source identity.

Перед удалением нужно прочитать собственные новые receipts и проверить delta
итогового source относительно этого audit. После отдельного reviewed retirement
обновить factual crosswalk/runtime records и пройти required CI на новом SHA.
Пользовательский actual-client acceptance этим source audit не проверяется.

## Manifest аудита

| Artifact | Git blob | UTF-8 SHA-256 |
| --- | --- | --- |
| `QUESTION_PLAN_V4_CONSUMER_AUDIT_130_134.json` | `34e59e3a6e6fd9e26865c7ae769590e5348b8cfa` | `d4cdbcc35d5903cfe9961971431dd85c6198313a4c852f82dea688504aed6a49` |

JSON: 502165 UTF-8 bytes. Все 2213 sorted path/mode/blob/size/content-hash rows:
`917e254bc7275d1927c557724769b2bb0d3f7b4d2eb81175d52d72b74a22e687`.
Полный tree roster3005 path/mode/blob/size rows:
`1f03563acc09b8e4b3e909240aa5d0e5ab2b51f2829b50aee3be497db4271e28`.

Оба audit artifacts предназначены для review. Production, tests, labels,
crosswalk status, commits и refs этим audit не изменены.
