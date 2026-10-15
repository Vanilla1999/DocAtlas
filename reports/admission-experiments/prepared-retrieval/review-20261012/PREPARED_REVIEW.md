# Независимое review prepared-parent reader

Дата: 2026-10-12. База: `47a636e73268f1c39495b83cda82c7a0a0c9674e`.
Область: подготовка, сертификат, чтение `ParentSection`, использование в
`SourceReferenceContext`; отдельно — доказательство фактического выбора reader.
Автор этого review не менял проверяемый продуктовый код и не запускал продукт,
pytest, модели или дополнительные поисковые эксперименты.

## Результат статического review

Блокирующего дефекта prepared-parent reader в проверенной области не найдено.
Это не заявление о проверке всех ветвей во время исполнения. Обнаружен пробел
в доказательстве: прежнее совпадение конечных packets при включённом и выключенном
флаге совместимо с постоянным parser fallback. Поэтому прежние четыре зелёных
сценария сами по себе не доказывали, что подготовленные строки действительно
переиспользуются.

Для закрытия этого пробела добавлен один ограниченный публичный интеграционный
сценарий. Код reader ради получения PASS не изменён. Исполнение и оценку сырых
результатов выполняет координатор после фиксации сценария.

## На чём основан вывод

### Подготовка сопоставляет строки с исходным parser

В `docmancer/core/_sqlite_store_part02.py` новые `parents` берутся непосредственно
из существующего `chunk_markdown_parent_child`; `source_id` одинаков у parent и
child одной исходной записи. При копировании неизменившейся части поколения оба
вида строк сохраняют прежний `source_id`. Идентификатор поколения меняется
согласованно у snapshot, parents и children.

`certify_prepared_parent_sections` в
`docmancer/core/prepared_parent_sections.py` сравнивает все hydrated
`ParentSection` с каноническим результатом parser и отдельно проверяет сохранённый
`display_text`. Для скопированных источников без результата writer parser
вызывается при подготовке. Простого хеширования произвольных сохранённых строк
для выдачи сертификата нет. Сертификат добавляется только к новому поколению со
статусом `building`, а не во время чтения активного legacy snapshot.

### Чтение связано с тем же snapshot

В `SourceReferenceContext._document` исходный текст извлекается из захваченного
`generation_sources`, а его SHA-256 проверяется до optional reader. Source ID
берётся из уже выбранных children того же поколения и источника. Reader не
обращается к изменяемой таблице `sources` для получения нового разрешения.

Manifest должен иметь подходящие schema, parser revision, generation ID и
validated status. В сертификате проверяются source identity и raw-content SHA.
Запрос к parents дополнительно ограничен теми же generation ID, source ID и
source. `parent_count` и digest полного упорядоченного набора защищают от
усечённого или изменённого набора строк. `parent_sections_digest` включает все
поля `ParentSection`; текст восстанавливается точным срезом уже проверенного
исходника и входит в digest через SHA-256. Загрузка дублированного `display_text`
на read path для этого не требуется.

Статического несовпадения ключей writer/reader, которое делало бы prepared hits
невозможными, не найдено. Snapshot со статусом `superseded` допускается только
как уже захваченная неизменяемая версия; `building` не используется reader.

### Отсутствие совместимого сертификата не меняет источник

Для отсутствующего manifest, несовместимого parser revision, некорректных строк
или несовпадающего digest reader возвращает явную причину промаха. Он не пишет
данные, не запускает индексацию и не разбирает Markdown. Caller использует
прежний parser над тем же проверенным текстом. Optional fallback не добавляет
источник в разрешённый каталог.

Переключение на prepared reader не исключает последующие проверки path/hash/span,
scope, generation и member binding в `SourceReferenceContext.prepare`. Кэш
`documents` и захваченный флаг ограничены одним `SourceReferenceContext`. По
завершении запроса они не становятся глобальным разрешением читать источник.

## Что новый сценарий проверяет

Файл: `tests/test_prepared_retrieval_review_integration.py`.
Публичная граница: существующий `call_docs_tool_payload("get_docs_context", ...)`
через helper `_context`; реальная member preparation, SQLite, retrieval,
selection и validation. Нет подмены этих компонентов, observer monkeypatch или
вызова приватного parser/reader из теста.

Использованы без изменений прежние `OPTICS_DOCUMENTS`, `OPTICS_QUESTION`,
`OPTICS_FACTS` и cap `12000`. Broad admission одинаков во всех четырёх reads:
сценарий изолирует reader и диагностику, а не повторно оценивает admission.

| Шаг | Reader | Трасса | Подготовленные данные | Проверка результата |
|---|---|---|---|---|
| 1 | Parser | Off | Совместимый manifest сохранён | Все четыре факта, исходные spans, допустимые источники |
| 2 | Prepared | Off | Тот же manifest | Полное совпадение стабильного публичного DTO со шагом 1 |
| 3 | Prepared | On | Тот же manifest | То же DTO; actual prepared hits > 0, parser calls = 0 в данном consumer |
| 4 | Prepared с fallback | On | Изменён только optional parser revision в manifest | То же DTO; причина несовместимости, parser calls > 0 |

Данные manifest изменяются непосредственно в изолированном тестовом SQLite как
подготовка сценария несовместимого cache. Исходные документы, raw snapshots,
строки parents, generation identity, каталог и права не меняются. До и после
каждого настоящего read проверяется логическое состояние всех таблиц и файлы
проекта относительно соответствующего подготовленного состояния. Fallback не
должен молча пересертифицировать или обновлять поколение.

Трасса переключается существующим `query_trace(enabled)`, поскольку значение
`DOCATLAS_TRACE` читается при импорте модуля. Тест читает реально выпущенные stderr
events после публичного вызова. При заданном `PYTEST_DOCATLAS_ARTIFACT_DIR`
сохраняются точные публичные packets и stderr каждого шага. Совпадение конечного
DTO и фактов обязательно; счётчики reader не заменяют эту проверку.

### Фиксация до исполнения

- Node: `tests/test_prepared_retrieval_review_integration.py::test_prepared_reader_reuses_rows_and_revision_falls_back_without_public_change`.
- SHA-256 тестового файла: `31fa8b09bd18f504be95a9c719ecda19ba9a55490b895c12a653ac451bdfa353`.
- Hash единственного node: `39b4f6cacdbebaacd42e1b9b31e7ffbfbf8da6734f4fedc9110b94de123887b5`.
- SHA-256 используемого fixture module на момент фиксации:
  `3945ebad4193795fabbe4cb737395d375cd25b641cf4c4e651704e7833a8d549`.
- Budget: **1 public prepare, 4 public context calls, 0 source reads, 0 model calls**.
- Диагностический sidecar: `tests/diagnostic_labels.prepared_retrieval_review.json`.

В fixture module параллельно усилены два assertions в других тестах; импортируемые
документы, вопрос, факты и helpers не изменены. Новый сценарий не вводит новые
формулировки вопроса, числа, предметные правила или исключения parser.

## Границы выводов

Даже успешный сценарий докажет отсутствие parser calls только внутри
`SourceReferenceContext._document` на данных четырёх вызовах. В общей цепочке
остаются другие consumers, разбирающие Markdown. Это соответствует согласованной
минимальной области реализации; глобальная структура документа пока не перенесена
целиком на index time.

Из совпадения DTO и reader counters нельзя вывести снижение медианной задержки
на 20% или общей стоимости, отсутствие любых downstream parses, качество ответа
генератора или обобщение на независимую новую предметную область. Коррупция digest
и другие причины fallback статически проверены, но новый runtime workload
намеренно содержит только один механизм invalidation — parser revision.

## POST_RUN: независимая проверка фактических результатов

Координатор исполнил сценарий в `run-02`; XML сообщает PASS. Автор review затем
прочитал четыре сохранённых публичных DTO, четыре файла native stderr и
сохранившиеся исходные файлы проекта. Продукт повторно не вызывался. Ниже
результаты проверки содержимого артефактов, а не вывод из одного exit status.

### Конечный контекст совпал во всех четырёх чтениях

Четыре packets этого node в `run-02-packets/`:

- `context-48849c9b6fb546c59df655422faeef7e.json`
- `context-4b3e8f8439bd4c08a91c656f93210ea7.json`
- `context-576ed15f463b4a45af0dfe454841693c.json`
- `context-b3ddb1ddde2e4815a3f23036a5bd7278.json`

Все четыре полных DTO совпадают, включая `source_uri` и `estimated_tokens`.
Предусмотренные тестом исключения этих двух полей для сравнения в данном запуске
не понадобились. Совпадают и полные файлы captured records; их общий SHA-256:
`5f359bb712e585907eb30fab71cb21b3f2bcca2d1a7c3e1641209140fcf48d93`.
Контрольный SHA-256 стабильного DTO после разрешённых исключений и канонического
JSON (`sort_keys=True`, `ensure_ascii=False`, separators `,`/`:`):
`5dbd20d9775c6d73f6cecb4445e08b3606182ca4bd1242e6492fba57579480ab`.

В каждом packet четыре source rows из двух разрешённых документов и **4/4
обязательных факта**: вместимость case, foam dividers, получатель issue record,
проверка и подпись перед отправлением. Проверены все 16 выданных row spans
относительно независимо зафиксированного исходного текста; каждого snippet
достаточно для однозначного нахождения в соответствующем исходнике, перекрытий
между двумя строками одного документа нет. Scope остаётся `project`, authority —
`source_of_truth`, evidence IDs уникальны внутри packet.

Сохранившиеся реальные файлы проекта также совпали с исходниками:

| Исходник | SHA-256 исходных байтов |
|---|---|
| `docs/packing.md` | `b07638e058cc56dfe9f22d9538e3fe16bcf6779c5bd4b61ca1b2832199487dfd` |
| `docs/issue.md` | `6153283d87fc5bbfa23994292ae4bc4ef5c10d1550f58f84aac1361e1c505aa9` |

Это hashes исходных файлов, а не значение публичного `content_sha256`, которое
здесь является fingerprint проекции. Объём каждой полной JSON-выдачи — **3262
UTF-8 bytes**, independently recomputed quarter proxy — **816**, cap — 12000.

Во всех packets `answer_supported`, `answer_available` и `edit_ready` остаются
`false`, качество контекста — `unverified`, coverage policy —
`retrieval_attribution_only`. Сохранение этих полей исключает превращение
подтверждённой доставки фактов в заявление о качестве сгенерированного ответа.
Дополнительные секции про архив и хранение также остались в packets; этот
сценарий не объявляет их необходимыми для ответа и не доказывает релевантность
каждого выданного блока.

### Prepared reader действительно использовался

Значения независимо прочитаны из native
`docatlas_query_trace.projection_observation.upstream_received.prepared_parents`:

| Поле | Совместимый manifest | Несовместимый parser revision |
|---|---:|---:|
| `documents` | 2 | 2 |
| `prepared_hits` | **2** | **0** |
| `parser_calls` | **0** | **2** |
| `parent_selects` | 2 | 0 |
| `parent_rows` | 4 | 0 |
| `incompatible_parent_revision` | 0 | **2** |

С совместимым manifest consumer получил четыре подготовленные строки двумя
SELECTs. При несовместимом revision он не читал parents и разобрал оба источника
старым parser. Конечный контекст при этом сохранился полностью. Это закрывает
прежний пробел: данный успешный результат больше нельзя объяснить постоянным
скрытым fallback.

Оба файла trace OFF пусты. Каждый файл trace ON содержит ровно один
`docatlas_request_start`, один `docatlas_query_trace` и один
`docatlas_request_end`. SHA-256 native stderr:

- `prepared-trace-prepared-on.log`:
  `200cdcdcee590b0576aff716412f0b05c5a498ddcfeca447b6d676f8d947bb48`.
- `prepared-trace-revision-fallback.log`:
  `6f567479b6f99bb24d5a363315681411dcc68de46b074dab9a3cdb97e02d0ffb`.

Фактический workload соответствует зафиксированному: **1 prepare, 4 context
calls, 0 source reads, 0 model calls**. SHA тестового файла после запуска остался
`31fa8b09bd18f504be95a9c719ecda19ba9a55490b895c12a653ac451bdfa353`.
Критерии и fixture для достижения этого PASS не менялись.

Проверки отсутствия изменений всех таблиц выполнялись в самом замороженном
интеграционном сценарии до/после каждого вызова. Их отдельные полные snapshots
не сохранены как внешние артефакты; этот аспект не перепроверялся reviewer по
одним DTO. Проверка raw source files после запуска описана выше отдельно.

### Что именно доказал запуск

На данном публичном сценарии **prepared reader реально заменил два повторных
разбора в `SourceReferenceContext` чтением подготовленных строк; при устаревшей
версии вернулся к parser без изменения выданного контекста**. Включение native
диагностики также не изменило публичный DTO.

Замер медианной задержки не выполнялся. Два prepared reads, проверка digest и два
parser calls относятся к разным ветвям единственного сценария; их отдельные
trace timings не дают основания обещать ускорение, тем более 20% для всей
цепочки. Другие consumers по-прежнему могут разбирать структуру. Вопрос был
заранее известен и переиспользован для изоляции reader; это не доказательство
обобщения admission на новые вопросы.
