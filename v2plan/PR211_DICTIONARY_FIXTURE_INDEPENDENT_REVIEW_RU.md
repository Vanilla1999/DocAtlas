# PR #211 — независимое review literal source fixtures

Дата: 2026-10-08. Reviewer: root, не автор slice. База:
`df9b682fdd13d8f4d1c5bff6cc4bfc0286e5f8ce`.

**APPROVE** для этих двух test modules и обычного CI. Blocking findings нет.
Runtime нового slice ещё **NOT RUN**. Approval не является утверждением о
27 новых PASS или о merge readiness.

| Файл | SHA256 |
|---|---|
| `tests/test_dictionary_exit_local_residuals.py` | `aa9f9a53a46a3132e1d0ee1fed24b24f518697fe459549c283440d4a24eaac3c` |
| `tests/test_dictionary_exit_read_tails.py` | `46757bae94a36f5ef1303e915bc249fadf23a0664c6313e3e9853c4aacc793f4` |

## Проверенный контракт

Прочитаны полный diff, действующий `SourceBoundary` с whole-declaration preflight,
`finite_local_path`, `collect_project_source_facts`, source-evidence producer и
`project_state._documentation_gap_evidence`. Добавлены только test-owned literal
members. Никакого сканирования дерева для получения разрешения, inferred membership,
production-code change или обхода validation нет.

Positive fixtures сохраняют исходные вопросы, explicit requirements и старые
ожидания. Новый source observer вызывает настоящий `Path.read_text` и сохраняет
hash прочитанного UTF-8 текста. До catalog источники не читаются; после него
прочитаны оба объявленных файла, а matching unlisted decoy исключён. Source path,
line bounds и snippet сопоставлены с существующим исходником.

В generated-positive fixture передан literal `True`; запрещённые members добавлены
в отдельные смешанные декларации. Excludes, gitignore, outside roots, vendor,
file/directory symlinks и oversized file проверяются реально существующими путями.
`finite_local_path` проверяет каждый такой member до yield первого пути; отказ
целой декларации здесь соответствует текущему контракту. Total scanned-byte
budget остаётся отдельной runtime границей, её whole-declaration свойство не
приписывается этому тесту.

Проверены дополнительные невакуозные controls:

- В nine-file fixture сначала доступны все девять явно объявленных исходников,
  затем gap producer сохраняет прежний шестифайловый предел. Порядок определяется
  существующим literal selection и path sort; новые ranking expectations не введены.
- Zero output budgets и disabled boundary проверяются также с валидной непустой
  декларацией, поэтому отказ не обеспечивается только отсутствием membership.
- Unsupported extension явно включён в отрицательную смешанную декларацию.
- Gap forwarding оставляет оригинальный query/whitespace, explicit unmatched
  context и отсутствие semantic completeness/edit authority. Это fixture migration,
  а не изменение recovery/admission.
- Прежние CRLF bytes, AST spans, cache isolation, redaction и отсутствие inferred
  status summary сохранены. Изменения не требуют semantic доказательства из prose.

## Независимый AST и baseline audit

Проверены frozen df9 files, реальные df9 Python 3.12 JUnit records и новый AST:

| Проверка | local_residuals | read_tails |
|---|---:|---:|
| Test functions сохранены | 16/16 | 12/12 |
| Изменённые функции | 8 | 3 |
| Старые assert AST сохранены | 57/57 | 55/55 |
| Assert AST после slice | 71 | 58 |
| Concrete baseline cases | 71 | 58 |
| Затронутые baseline FAIL cases | 24 | 3 |

Names, порядок и decorators прежние. Удалённых test nodes/assertions нет;
skip/xfail/parametrization и diagnostic inventory не меняются. Добавлено 17 assert
AST. AST compile без исполнения и `git diff --check`: PASS.

34 отдельных generated-parameter failures не менялись: они требуют отдельного
разбора partial-filtering против whole-declaration preflight. Два recovery
truncation cases также не менялись. Deferred retrieval, frozen gold, старый ABI
и production caps этим slice не затронуты. Поэтому общий результат должен
сравниваться с baseline по каждому concrete node, сохраняя эти failures видимыми.

Pytest, package installation, providers и реальные runtime/client subprocesses
локально reviewer не запускал. Обязателен общий CI на опубликованном SHA.
