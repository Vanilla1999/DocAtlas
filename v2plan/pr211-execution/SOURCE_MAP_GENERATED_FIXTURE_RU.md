# SourceMap generated fixture: finite membership и явный opt-in

## Причина и текущий контракт

Один старый positive ожидал, что вопрос `Inspect the generated file GeneratedModel` сам разрешит прочитать `generated/model.py`. Текущий `collect_project_source_facts` требует одновременно finite `code_files` и строго boolean `include_generated=True`. Обычный текст вопроса не предоставляет source grant. Excludes продолжают действовать и при generated opt-in.

Production `source_map.py` (`6cc977084fcd321184046bf0f59ad6ee1b4fa973`) и `source_boundary.py` (`50dc209c6a9b9598dc676bd6ed557d9be21301b6`) непосредственно прочитаны и не меняются.

## Миграция существующего node

Изменён только `test_source_map_includes_generated_path_for_explicit_artifact_question` в `tests/docs/test_source_map.py`. Исходные имя теста, вопрос, путь и bytes `class GeneratedModel: pass\n` сохранены.

- Positive явно записывает единственный разрешённый `generated/model.py` в fixture catalog и передаёт boolean `True`.
- Exact path, class identity, строки 1–1, полная длина прочитанного исходника и SHA-256 фактически прочитанных bytes проверяются.
- Отдельный `generated/other.py` остаётся вне finite grant и не читается.
- Один opt-in без catalog даёт пустой результат без source reads.
- Один catalog при `None`, `False` или строке `"true"` также не разрешает source reads, несмотря на тот же вопрос.
- Явный exclude `generated/**` продолжает запрещать чтение при `include_generated=True`.

Используются существующие `_declare_code_files` и observer `_observe_source_reads`. Observer сохраняет и проверяет hashes после реального `Path.read_text`, а не подменяет parser или содержимое. Новых test functions, skip/xfail или production exceptions нет. Все 29 имён функций и их порядок сохранены; diagnostic node identity не меняется.

## Состав и проверка

База чтения: `841e770e644dba369ab441ba2ec9f2a8807cac7f`.

| Путь | Исходный blob | Proposed blob |
| --- | --- | --- |
| `tests/docs/test_source_map.py` | `d6208cefc0e62daa175be3d29670a258e7cefa71` | `03245a209014d8d6b2fed4daf5cbba0bab2c4fd5` |

Проведён source review пути `collect_project_source_facts → iter_bounded_source_files → finite_local_path`, strict boolean opt-in, whole-declaration preflight, excludes и точного symbol DTO. Изменение теста прочитано отдельно от production.

Локальные imports, AST/compile, pytest и server calls не запускались. Это reviewed fixture migration, runtime-результат требуется получить в обычном CI на опубликованном SHA. Прохождение других SourceMap cases и full acceptance этим файлом не утверждается.
