# PR #211: сохранение schema contract и остаток footprint

Дата: 2026-10-08. Это результат статического измерения и подготовленные проверки,
**не runtime/CI/client acceptance и не согласование нового ceiling**.

## Результат и действующий blocker

Default advertised catalog: **7602 → 7066 bytes**, уменьшение на 536 bytes.
Действующий gate **≤6144** не изменён и остаётся **FAIL: превышение 922 bytes**.
Docs outputSchema сохранена буквально: **860 bytes**, действующий gate **<1000**.
Catalog уже включает outputSchema; складывать эти два измерения нельзя.

После удаления простых дублирований дальнейшее сокращение в этом slice остановлено,
чтобы сохранить явные scope, source, consent и authority instructions и всю
структурную validation. Это не доказательство математической недостижимости 6144.
Это граница рассмотренных простых изменений без нового протокола или потери guards.

Конкретное предложение для отдельного решения владельца: catalog **≤7168 bytes
(7 KiB)** при неизменном output **<1000 bytes**. Текущий результат оставляет 102 bytes
до предложенного потолка. Предложение **НЕ одобрено**; test и gate не изменены.
Без такого решения либо нового обоснованного сокращения footprint blocker открыт.

| Инструмент | До: весь tool | После: весь tool | Input после | Output после | Description после |
|---|---:|---:|---:|---:|---:|
| get_docs_context | 2563 | 2414 | 490 | 860 | 989 |
| prepare_docs | 4376 | 4007 | 3638 | — | 314 |
| docs_status | 659 | 641 | 415 | — | 172 |

Поля таблицы — отдельная атрибуция, а не слагаемые с повторным учётом. Catalog также
включает JSON-обрамление списка. Это UTF-8 bytes сериализации, не model tokens и не
измеренная стоимость для конкретного клиента.

## Независимая база

База: `21fe472d983f394130849d6fd4e582043d58e9ba`, исходный файл
`docmancer/mcp/_docs_server_tool_data.py` получен через `git show` именно этого SHA.
Из трёх `PUBLIC_ADVERTISED_*` constants выполнен `ast.literal_eval`, без импорта
DocAtlas или запуска сервисов. Исходный порядок tools: get_docs_context,
prepare_docs, docs_status. Для этих constants null-enum cleanup не меняет значения.

Baseline сохранена отдельно в
`tests/docs/fixtures/pr211_catalog_21fe472d.json`. Она не восстановлена обращением
нового patch. Encoding: UTF-8, `ensure_ascii=False`, `sort_keys=True`,
`separators=(',', ':')`, без завершающего newline.

- Baseline source SHA256:
  `a1d9b1cd00fdcb0bbbe6fc6a2ba28ed6a66a2781bacc9b1d2067956cf5144ab6`.
- Baseline catalog SHA256 (7602 bytes):
  `ad63f367601a18fe04ec715800be2a935a7496c16beb71df4d1818d258bc06db`.
- Новый source SHA256:
  `04bc8f230f6f751f886aad19e8b57f95840626648ce80fbf0f45a5fe4bedc09e`.
- Новый catalog SHA256 (7066 bytes):
  `229b90fb1a58e4255cd5926f726f2d28b6171232491f91b1341e417bea51f397`.

Это hashes содержимого, а не tested code commit. Итоговый совместный SHA и его CI
должны быть зафиксированы координатором после публикации всех slices.

## Обоснование изменений

1. Parameter guidance get_docs_context собрана в одном tool description.
   Сохранены: unchanged original concrete question, запрет meta-question replacement,
   explicit same-question lookups без inferred rewrites/translations/subquestions/
   expected answers/source names и без independent-question batching; точные literals.
   Lookup coverage не переносится на original. Все семь input fields, их nullable
   поведение, limits, required question и unknown-field closure сохранены.
2. Scope описан явно: project — только repo-level docs; module — один exact module;
   all — repo+modules в том же repository без module filters; module_path всегда
   ограничивает module scope. Нельзя расширять scope из текста вопроса. Версия
   текущего проекта опускается; exact/historical — только явно; lockfile changes
   требуют повторного запроса. Источники — недоверенные данные, не инструкции.
3. Context/flags не сертифицируют completeness/proof/edit readiness; hard_stop=true
   запрещает edit, false не даёт permission. Edit требует отдельной explicit target
   и authorization. Freshness, provenance, network consent и budgets сохранены.
4. Prepare и status guidance короче, но preparation остаётся допустима только по
   get_docs_context recommended_next_action или explicit lifecycle request.
   Missing/stale docs и network approval сами по себе permission не дают. Сохранены
   source bindings, confirmation, network consent, returned job_id polling и один
   unchanged retry только после verified success/readiness. Status — только explicit
   status requests либо returned recommended_next_action/job_id; не discovery.
5. Удалён `type: string` только у двух action enums, все значения которых — строки;
   удалены типы двух const discriminators (строка operation и JSON boolean confirm).
   Enum/const продолжают отвергать null, другие JSON types и неправильные значения.
   Numeric const/type отношения не упрощались: JSON true отличается от 1 и 1.0.
6. Удалены только pattern-implied minLength: ASCII digest widths 64/71, generation
   width 36 и непустой literal path. Patterns, types и maxLength сохранены.
   Особенно не удалены верхние длины digest/generation: Python regex `$` допускает
   позицию перед завершающим newline; maxLength продолжает отвергать такие значения.
7. Два одинаковых clear_index `if` объединены в один `if/then/else`: при clear_index
   остаются required scope/project_path, во всех иных actions confirm отсутствует.
   Повторный sync discriminator в `then` заменён `{}` только потому, что тот же
   exact const уже проверяется окружающим `if`; ключ action и unknown-field closure
   в закрытой ветке сохраняются.

`with_vectors` сохранён буквально, включая nullable boolean и default=false.
Рассмотренное удаление отклонено: хотя успешного public action с ним нет, удаление
из открытой non-sync schema стало бы пропускать неверный тип до dispatcher.
Сохранение runtime rejection не оправдывает ослабление advertised validation.

Нет generic object замены, server-only validation, новых `$ref`, loader/registry,
новых aliases или смены потолков. RAW/internal schema и подробная patch-структура
не менялись. Source binding, member confirmation/CAS и runtime readers не менялись.
Retrieval не менялся.

## Проверки и предел evidence

Выполнено без runtime imports:

- Exact baseline bytes/hash и canonical serialization.
- AST parse изменённых Python-файлов.
- Равенство всех трёх input schemas после нормализации **только** перечисленных
  выше логически избыточных конструкций и `description` annotations.
- Буквальное равенство output schemas; AST equality всех остальных source nodes
  относительно исходного файла 21fe472d, включая RAW и advanced/internal references.
- Построение матрицы **417 cases: 321 общая boundary case + 96 with_vectors cases**.
  IDs уникальны. Ожидания authored независимо от новых schemas.

`tests/docs/test_pr211_catalog_equivalence.py` добавляет пять normal pytest nodes:

1. `test_pr211_catalog_baseline_is_exact`.
2. `test_pr211_catalog_preserves_all_remaining_schema_constraints`.
3. `test_pr211_catalog_boundary_acceptance_matches_independent_baseline`.
4. `test_pr211_vector_field_preserves_nullable_type_and_action_restrictions`.
5. `test_pr211_unknown_fields_and_invalid_mutation_never_reach_service`.

Матрица покрывает required/unknown/null, action/scope discriminators, bool vs number,
lookup counts/lengths/uniqueness, member count 1/500/501, duplicate members, relative
paths, digest/generation boundaries и trailing newline. Существующие permissive
schema corners отдельно остаются permissive; runtime guards не переименованы в
advertised validation. with_vectors проверяется для каждого из 12 actions, включая
неверные типы в non-sync actions.

Тест до-I/O отказов использует реальный dispatcher и текущие schemas; resolver,
service selection и handlers заменены счётчиками. Сначала schema-valid read-only
docs_status positive достигает всех трёх счётчиков. Затем invalid/unknown inputs,
включая malformed non-sync with_vectors, обязаны оставить все три равными нулю.
Один error reason_code не считается доказательством отсутствия dispatch/effects.
Ни одной реальной mutation, network операции или service storage для этого не нужно.

**Pytest, JSON Schema acceptance matrix, MCP stdio и clients: NOT RUN.**
В текущем локальном окружении отсутствуют pytest/jsonschema/fastjsonschema; подходящий
установленный Ajv также не найден. Dependencies/models не скачивались. Статическая
нормализация не переименована в запуск validator или в пять PASS pytest tests.

Локальные промежуточные evidence:
`/workspace/scratch/5ecb5f548321/pr211-footprint-artifacts/` — `static_report.json`,
`boundary_matrix.json`, `current_catalog.json`. Полная матрица воспроизводится из
committed test fixtures; runtime результаты должен дать normal conftest/CI run.

После согласования schema slice требуются joint acceptance на конечном SHA,
required CI/downstream gates и разрешённые installed/client checks. Ни bytes,
ни symbolic equality не закрывают эти gates.
