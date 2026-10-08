# PR #211 — independent review generated membership successor

Дата: 2026-10-08. Reviewer: `membership_fixtures`, независимо от root-author.
База сравнения: frozen `f0ed956ce2c2ba19dc536bbe0ad6dbebb8418fa4`.
Вердикт: **APPROVE** для двух test files с точными SHA256 ниже.
Неразрешённых findings по этому slice нет. Это review изменений tests, не
заявление runtime PASS новой версии или full CI acceptance.

## Прочитанное основание

Проверены полный diff двух modules, author report, действующие
`SourceBoundary.from_project`, `iter_bounded_source_files`, `finite_local_path`,
catalog reader и настоящие source-map entrypoints/capture readers. Прочитан
исторический `LOCAL_MEMBERSHIP_IMPLEMENTATION_RU.md`: конечный явный code set,
preflight до чтения, запрет discovery и сохранённый literal generated consent
уже были частью интегрированного контракта.

Три названных author report controls реально существуют в
`tests/test_dictionary_exit_local_membership.py`:

- `test_invalid_literal_member_fails_whole_catalog`;
- `test_finite_membership_preserves_boundaries`;
- `test_generated_read_requires_literal_boolean_consent_and_finite_member`.

Catalog без valid finite `code_files` не открывает source reads. Iterator
сначала проверяет каждый объявленный путь; запрещённый generated member при
любом значении кроме literal `True` прекращает всю декларацию до первого yield.
Допуск generated при `True` сохраняет остальные source boundaries. Само
упоминание generated в question/requirements или наличие файла на диске не
является membership или consent.

Старый assertion «normal есть даже в запрещённой mixed declaration» отражал
предыдущий traversal-контракт. Его нельзя объявить буквально сохранённым после
whole-declaration preflight. Author report явно описывает этот successor и не
подменяет прежнее поведение молчаливой выдачей actual value за expected.

## Проверка двух независимых controls

В обоих tests список двух declarations задан константами: полный mixed set,
затем normal-only set. Обе фазы выполняются для каждого параметра. Флаг и query
не участвуют в построении membership; результаты API также не определяют grant.
Замена catalog между фазами — явная подготовка следующего test control, а не
новый production retry или auto-pruning после denial.

В mixed set обычный файл стоит перед generated. Поэтому отказ с `rows == []`
и пустым observer действительно проверяет отсутствие частичного чтения до
встречи запрещённого следующего member. `None`, `False`, `1` и `"true"` в local
matrix не превращаются в consent; read-tails сохраняет свои `None/False/True`
и все восемь исходных вопросов. При literal `True` exact path set должен
содержать обычный и все объявленные generated files.

Во второй фазе все исходные generated files остаются на диске. Вопрос,
requirements и флаг прежние, но authored membership содержит только ordinary
file. Exact path set и actual read dictionary требуют именно этот файл для
каждого параметра. Даже `True` вместе с буквальным generated path не разрешает
прочитать unlisted generated source. Таким образом положительный смысл old
ordinary-file assertion остаётся проверяемым в валидной отдельной декларации.

Оба observers вызывают исходный `Path.read_text` и возвращают настоящий текст.
Они не подменяют catalog, iterator, fact extraction или результат API. Expected
SHA256 вычислен из authored file bytes до установки observer; observed SHA256
вычислен из реально возвращённого UTF-8 текста. В этих ASCII/LF fixtures обе
величины относятся к одним и тем же bytes. Это проверка локального fixture
чтения; нового authentication/hash-binding API она не заявляет.

В local matrix один выбранный collector вызывает capture; expected list для
каждого разрешённого файла содержит один hash. В read-tails отдельно вызваны
facts, repo-map и snippets, без shared `source_facts`: статически проверенный
call chain читает файл один раз на каждый entrypoint. Expected multiplicity
равна трём. Все положительные expected dictionaries непустые. Observer очищается
до каждого control, не после вызова collector. Source extensions покрывают все
созданные файлы; YAML/config reads не выдаются за source reads.

## Scope / inventory

Stdlib AST сравнение выполнено с чистым frozen f0 checkout:

| Module | Existing test names | Единственная изменённая function | Assertions в ней |
|---|---:|---|---:|
| `tests/test_dictionary_exit_local_residuals.py` | 16/16 | `test_generated_requires_boolean_true_even_for_explicit_path` | 2 → 4 |
| `tests/test_dictionary_exit_read_tails.py` | 12/12 | `test_only_explicit_generated_opt_in_authorizes_source_scanning` | 4 → 4 |

Все decorators, их параметры и порядок test names совпадают. В signatures
добавлена только pytest fixture `monkeypatch`. Остальные functions, включая
helpers и ранее reviewed 27 cases, совпадают AST-exact. Остальные top-level
statements сохранены. Единственные новые imports — `hashlib` и `Path` во втором
module для observer. Шесть retired assertions имеют восемь явно обоснованных
successors; утверждения о неизменности всех прежних assertions здесь нет.

Concrete matrix identities остаются 10 + 24; новых/удалённых test names нет.
Diagnostic shard bytes не менялись, и независимо вычисленные hashes совпали:

- local-residuals, 16 unique base nodes:
  `7e6638ecd1837b5aef4258417def41888f0e275681e3c97daf962a8947cd9be2`;
- read-tails, 12 unique base nodes:
  `6f45004bf3b4b59b830fd5fa92cc324efafbc1ce1c9c3e5d135cd1b6afeaaa59`.

Новых skip/xfail, selector, gold, output/scan limits или CI gate changes нет.
SourceBoundary, catalog producer, retrieval, admission, ranking и mutation
protocol этим slice не меняются. Сохраняются внешние controls исключений,
symlinks, roots, scrubbing, byte/line bounds и request-local cache isolation.

## Runtime evidence и предел review

Независимо скачанные JUnit из обычного f0 CI
[37819292857](https://github.com/Vanilla1999/DocAtlas/actions/runs/37819292857)
подтвердили: все эти 34 cases всё ещё FAIL на f0 во всех Python
3.11/3.12/3.13; ранее reviewed dictionary27 уже PASS. Поэтому review не
переносит зелёный статус прошлой fixture migration на новый successor.

Новая версия **NOT RUN**. Локальных repository imports, pytest, package installs,
provider/client calls или runtime subprocesses reviewer не выполнял. Выполнены
read-only source inspection, AST/inventory comparison и `git diff --check`.
Все author-report links и названия приведённых existing controls проверены.
Reviewer записал только этот report, production и tests не редактировал.
Обычный CI будущего общего SHA должен подтвердить оба controls и отсутствие
прежних PASS regressions.

## Exact reviewed bytes

| Файл | SHA256 |
|---|---|
| `tests/test_dictionary_exit_local_residuals.py` | `3bf37fe379bae8767e664ad91e6fed48375a1c123ab0073ee6f13b5272e98181` |
| `tests/test_dictionary_exit_read_tails.py` | `e8c6761b947c23e5237dc7c709eb9ff33dccc521c93a2b61225e7de854a6dec7` |
| `v2plan/PR211_GENERATED_MEMBERSHIP_REVIEW_RU.md` | `e7429f36bf743bdf7210187bd9410ce67052be9049081f4f29060d0c11e4b8c5` |
