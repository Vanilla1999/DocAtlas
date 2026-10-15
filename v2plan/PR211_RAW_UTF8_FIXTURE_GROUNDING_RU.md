# PR211: raw UTF-8 grounding в общей native fixture

## Причина и граница изменения

Это миграция проверки fixture после raw-window slice 133, а не изменение retrieval или acceptance gold. База: commit `7b56e7b61ff28024349ae13d8e60a591788b83cf`, tree `0efae221bcb7a65e1cf18a3e6525f0f9146c89e0`.

`capture_fixture` проверяет, что каждый доставленный snippet находится в строковом окне реального файла выбранного проекта. Прежние `read_text(...).splitlines()` и последующий `"\\n".join(...)` меняли проверяемый источник: универсальное чтение нормализовало CRLF, а сборка удаляла конечный перевод строки. Полный raw snippet с собственным конечным LF/CRLF из slice 133 поэтому мог не оказаться подстрокой искусственно нормализованного окна. Это source-level несовместимость двух контрактов; конкретный результат всех native cases на новом SHA ещё не получен.

Исправление состоит ровно из двух строк:

1. Читать те же байты файла через `read_bytes().decode("utf-8").splitlines(keepends=True)`.
2. Собирать выбранные строки через `"".join(...)`.

Декодирование остаётся строгим UTF-8. Никакого `strip`, удаления переводов строк из actual snippet, поиска по другому файлу или обхода ошибочных координат нет.

## Сохраняемые проверки и работа

Сигнатуры `capture_fixture` и `visible`, все вопросы, authored documents, lookup inputs и native вызовы сохранены побайтно. На каждый source чтение существующего файла заменено другим способом чтения того же файла; дополнительных native reads, indexing, retrieval, resolver, projection или validation calls не добавлено.

Перед containment остаются разрешение пути и `is_relative_to(root.resolve())`, точный тип `int` для обеих координат и условие `1 <= start <= end <= len(lines)`. Сам containment остаётся строгой проверкой фактически доставленного `source["snippet"]` внутри окна с этими координатами. Этот helper подтверждает подстроку в указанном окне; отдельную гарантию полноты всего окна он не подменяет.

Все проверки false answer/edit authority, текущего projection snapshot и `validate_model_visible_projection` сохранены. Обработка source identity, digest и optional continuation URI не изменена. Формат production source и глобальный formatter также не изменены.

## Проверенные consumers

Прямые импорты helper найдены в объявленном source inventory 130: 2213 paths, 2128 прочитанных различных blobs, 0 unread. Peer выполнил bounded поиск буквального имени `_global_evidence_fixtures`; ниже все шесть code consumers. Точные SHA повторно сверены с tree 134; четыре ранее не прочитанных caller-файла прочитаны отдельно. Проверка относится к буквальным ссылкам и не претендует на обнаружение произвольно вычисляемых import names.

| Consumer | SHA на 134 |
| --- | --- |
| `tests/docs/_reference_binding_fixtures.py` | `7fd30e607488b9841e3fd78f146af737c6c1c04e` |
| `tests/docs/test_context_projection_boundaries.py` | `61e303d5d9686f1f19a3809e104e6f9975b1fdba` |
| `tests/docs/test_need_local_admission.py` | `60c30a0282d3ff03a49097d7c002633911b25745` |
| `tests/docs/test_query_block_guards.py` | `5100517fdb6635ad3bd2f5304b49fdf553ee3533` |
| `tests/docs/test_requested_evidence_retention.py` | `1e119ed9e09864e05f8962260c7c893bec9bcf6a` |
| `tests/docs/test_source_bound_subject_context.py` | `0c8e6a25a6aecc9d6a71f7b3ca122a498e5cc550` |

Через `_reference_binding_fixtures` дополнительно сохраняются все 14 найденных consumer-модулей. В частности, `test_reference_behavior_matrix.py` остаётся с исходными 6 функциями / 24 cases: это проверки доставки command facts, source identity, project isolation и отрицательных source guards. Их 24 public reads / 25 indexing calls / 24 isolated service contexts не свёрнуты в один новый тест. Исправление helper само по себе не объявляет эти 24 cases успешными и не разрешает их удаление.

## Manifest и статическая проверка

| Path | Mode | Base blob | Proposed blob |
| --- | --- | --- | --- |
| `tests/docs/_global_evidence_fixtures.py` | `100644` | `ce01e23f813c876921be2995f2ce19e906e3c27d` | `3c553de307522ff40a2cdfc598876d71bd83065a` |
| `v2plan/PR211_RAW_UTF8_FIXTURE_GROUNDING_RU.md` | `100644` | new | этот документ |

- SHA-256 исходного helper: `414249b0a5664c2b90df292ce13bb18834196eecc037e3ecb83bac81daf3b9dc`.
- SHA-256 нового helper: `64737993be919bd8d50e89a5265c808b909065e235999f60910d5e4ac0eadf99`.
- Обратная замена только двух указанных строк восстанавливает исходный helper побайтно.
- GitHub blob helper перечитан; roundtrip exact.
- Новых test functions и параметризаций нет. Shared helpers и caller imports не удалялись.
- Локальное исполнение, Python imports, pytest и дополнительные runtime прогоны не выполнялись.
- Independent static review и совместный CI на опубликованном SHA нужны отдельно. Новый runtime PASS здесь не заявлен.
