# PR211: retirement только 21 Context7 topic-alias case

## Изменение и граница

После собственного успешного normal critical proof удаляется только
`test_russian_newcomer_queries_get_retrieval_only_aliases`: одна функция,
21 параметризованный случай, исходные строки 20–51 вместе с декоратором.

В `tests/docs/test_context7_style_project_chat.py` остаются все остальные
18 функций / 36 случаев. Их тела, декораторы, исходные вопросы, assertions,
все imports, класс `_EmptyRequirements`, другие non-test statements и
пробелы вне удаляемого span сохранены побайтно. Вставка ровно удалённых
32 строк на прежнее смещение полностью восстанавливает исходный модуль.
Все 70 случаев `tests/docs/test_documentation_query_plan.py` сохранены.

Отдельных обычных test functions не добавлено. Existing independent control,
его normal 53-case roster, critical runner и production не изменяются.

## Почему эта семья допускает retirement

Вся выбранная функция требовала от свободного вопроса непустой alias с
заранее заданным dictionary topic: `intent_id`, `force_context_only`,
непустой `text`. В ней нет source body, проверки факта, native retrieval,
доступа, lifecycle или finite membership. Действующий
`build_project_retrieval_aliases` возвращает пустой tuple; авторский
`lookup_queries` сохраняется отдельно в текущем query plan.

Все 21 исходный вопрос и historical intent IDs остаются в точном raw archive
`eval/task_level/contract_history/context7_newcomer_alias_inputs.py.txt`
и его frozen crosswalk. Архив содержит полный старый модуль, а не пересказ.

Действующий один control
`test_current_alias_boundary_preserves_explicit_queries_without_inference`
проверяет прежние 3 вопроса и эти 21 — всего 24 неизменных вопроса. Для каждого
сначала выполняются здоровые проверки original/explicit lookup identity и
отсутствия заимствованного original-query credit, затем alias guards.
Он извлекает только literal decorator data из архива; старые assertions не
исполняются. Все остальные top-level nodes рабочего модуля сравниваются
с архивом; выбранная функция уже допускается в количестве 0 или 1.

Эта замена не доказывает фактическую полноту retrieval, качество natural
questions, finite admission, source authority, installed clients или MCP.
Все такие оставшиеся обязательства сохраняются.

## Фактический normal proof до retirement

- PR head: `f7b9253c8e477babf276ae8dd2cb18905451cd15`.
- Фактический checkout merge: `011e808a0dcd2ec8104611a2257d17b5f20e327a`.
- Родители merge: `d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c` и указанный PR head.
- Checkout tree и PR-head tree одинаковы:
  `cfe816a4e295961b2b529b612bbc63c39ff99ccf`.
- Run `38008532239`, attempt `1`,
  [advanced job 114082885405](https://github.com/Vanilla1999/DocAtlas/actions/runs/38008532239/job/114082885405).
- Normal baseline: **53 PASS, 0 FAIL, 0 ERROR, 0 SKIP**; returncode 0.
- Все **20** directed mutations получили ожидаемое число failures в своих
  выбранных tests, без errors/skips. У 18 указан named guard; два сохранённых
  legacy targets имеют `failure_guard: null`. Final receipt: baseline green; 20 killed.
- Baseline roster:
  `b4a630000b9791fdb09c4b245bc2b213cba2cb8914b1898bc58116354cc5d585`.

Новый `context7_russian_topic_router_cannot_generate_aliases` срабатывает
только на новых archived inputs 0/1 и недостижим для прежних трёх вопросов.
Фактически: 1 test, 1 expected FAIL, 0 ERROR, 0 SKIP, returncode 1,
`anchor_count=1`, guard `critical_context7_no_topic_router_aliases`.
Его killer — тот же существующий independent control. До этого guard все
здоровые original/lookup проверки завершаются.

- Mutated source:
  `docmancer/docs/domain/project_retrieval_intent.py`.
- Before SHA-256:
  `d1940e93bf701033bf57ca3f0e3fe767326a275e497c1ece28d2154b3c489248`.
- After SHA-256:
  `7f9bb4c33c117987145c058a6f5860744eb5eaa3ee8ad08c19948957b7b9e25f`.
- Alias target roster:
  `8da8e109f727ed0e60616bd1252127b9f431cf18eec4060eaa0e0e19846eac2a`.

Прежний unconditional alias mutant также получил свой прежний
`critical_alias_no_generated_queries`, 1 expected FAIL / 0 ERROR / 0 SKIP.
В crosswalk добавлены value-exact normal baseline и обе alias mutation
записи, а также исходы всех 20 normal mutations. Historical comparison
записи с `case_mode` исключены из этого proof.

## Collection и внешний аудит

На точном f7 tree прочитаны **1547 source/config файлов**, включая все
1273 tracked Python files и 39 workflows. Дополнительно охвачены shell,
YAML/TOML/INI/CFG, Makefile/Justfile и root/.github/scripts/diagnostic JSON.
Каждый fetched blob SHA сопоставлен с exact Git tree; ошибок чтения нет.

Искались имя модуля, удаляемая функция и `_EmptyRequirements`.
Внешних pytest selectors или imports удаляемой функции нет. Кроме самого
модуля найдены только diagnostic shard, существующий archive control и
исторический `p0_transition_manifest.py`, который перечисляет сохраняемый
файл и не содержит selector удаляемого node. Markdown и corpus/result JSON
не представлены как проверенные executable selectors.

Digest полного exact path/blob roster:
`a3ab23683bb21796d923380d1eda5eaf8b1235d39e4bb23c368e23e93820d7d7`
(SHA-256 UTF-8 sorted `path:blob_sha`, соединённых newline без финального newline).

Diagnostic shard сохраняет behavioral label и registration модуля.
Меняется только hash состава имён tests:

- 19 прежних nodes:
  `9a242ae667d5864e13ac4a9bf952ae7015f922ed877e5717814be46625844c84`.
- 18 оставшихся nodes:
  `96fdabc9cf426155e59d28ec756951ffc5a81cd2e47bf0b3d92adbed43b230d9`.

## Честная граница acceptance

[Full core reader 114085424570](https://github.com/Vanilla1999/DocAtlas/actions/runs/38008532239/job/114085424570)
самостоятельно прочитан для того же f7 run: каждый Python 3.11/3.12/3.13
имеет **6057 PASS, 1680 FAIL, 0 ERROR, 10 SKIP**; integrity issues пусты,
`omitted_rows=0`. До retirement Context7 имеет **12 PASS / 45 FAIL**.
Это не зелёный full core. Результаты после изменения diagnostic roster
и удаления 21 case ещё не получены.

Для конечного SHA остаются normal critical 53/20, корректная collection
полного core и остальные required downstream/installed/client gates.
Никакое предполагаемое уменьшение FAIL не записано как фактический PASS.
Локальные runtime, imports, pytest и install не выполнялись.

## Exact review manifest

| Путь | Base blob | Proposed blob |
|---|---|---|
| `tests/docs/test_context7_style_project_chat.py` | `6a9e2564f60b696e2e6f64e5f53512728f9e6c34` | `fd735fdf7402925417ca76ef591f125f2408f6e7` |
| `tests/diagnostic_labels.context7_project_chat.json` | `f242c5f4d8a15e5f05994e924d103da52d1820b1` | `96fff3f3631357da09971115a820b3277a5fa78d` |
| `eval/task_level/contract_history/context7_newcomer_alias_inputs.json` | `1247a6857fa76388f91ac4827ebaafa954c75786` | `c3ba112a5278e37ee4de1725e1e9ff09e4824ec2` |

Все изменяемые файлы имеют mode `100644`. Новый этот note — тоже `100644`.
Control `17f64832f9fe7a4d7532ebb0fe6b6ffbfb81dc8d`,
runner `8f31dfccd02025b8355020aa4063952733c0689a` (mode `100755`),
raw archive `6a9e2564f60b696e2e6f64e5f53512728f9e6c34` не изменены.

Crosswalk сохраняет все прежние поля precheck value-identical, кроме
`migration_status`; их pending/collected wording — исторический snapshot
base 80c8. Текущее состояние и фактическое доказательство находятся в новых
`retirement` и `runtime_proof`; frozen inputs, offsets, gold history,
source hashes и prior receipt не переписаны.

## Независимый review

Contracts и root: **APPROVE** exact code/diagnostic blobs и границу удаления.
Independently проверены inverse, remaining nodes, current control, scoped mutation
и его фактический source-bound receipt. Полный 1547-file scan — отдельно
авторский аудит; peer проверил известные внешние consumers, не повторяя весь scan.
Root уточнил metadata: `proof_input_blobs_at_runtime` описывает входы прошедшего
прогона, а не обещает неизменность последующих working files; 18 named guards
отделены от двух сохранённых legacy targets без named guard.
