# PR211: миграция проверок сохранности найденных окон

## Причина и текущий контракт

На опубликованном CI130 (`0065ce62`, run `38024963940`) модуль
`tests/test_action_packet_v4_found_window_retention.py` дал 31 PASS / 6 FAIL
из 37 cases. Наблюдения сохранены в `RUNTIME_EVIDENCE_0065ce62.json`.
Пять функций содержали предположения о меньшем обычном ответе; два failures
приходятся на параметризации одного noncopyable-requirements теста.

Правильный контракт установлен по текущему production source:

- `_project_docs_service_part03.py`, blob `7b17f564732ab7c5f712e4091bf0dfe3e4a7d617`:
  выбор уже приобретённых независимо квалифицированных окон не обрезается
  presentation-квотой; `limit` и retrieval budget остаются параметрами acquisition.
- `_project_context_service_part01.py`, blob `ca3a36829898bd76d3a21afd82f2f0bd92881e90`:
  ordinary read сохраняет такие окна в `read_presentation_pack` после тех же
  consent, lifecycle, dependency, stage и delivery проверок.
  Его project-doc control view, selection и routing сохраняют свои ограничения.
- `project_doc_ranking.py`, blob `b2cfa8385c2381cd93fc507a35e61b1cc1e33ca9`:
  patch retention дополнительно требует завершения конкретного вызова
  с тем же returned object и sinks. Контракт completion не определяется
  сравнением количества элементов с ordinary read.
- Вызов без ACK не делает snapshot аргументов: непереносимый объект requirements
  передаётся dispatcher по той же ссылке. Это действует для omitted, false
  и unacknowledged-true вариантов.

Поэтому `32 > 32` и ожидание четырёх результатов при 32 подходящих acquired
окнах не являются действующим требованием. Искусственная потеря source facts
ради старого сравнения не вводится.

## Изменённые проверки

Все исходные authored files, вопросы, parameter values, helpers и 26 test
definitions / 37 collected cases сохранены. Это миграция пяти функций,
без удаления тестов и без новых native calls.

| Функция | Новая проверка |
| --- | --- |
| `test_final_merge_retains_qualified_windows_without_changing_acquisition` | Ordinary и explicit-retention результаты содержат ровно исходные 32 stable IDs и полные raw bodies из fixture; прежний exact control view и acquisition trace также совпадают. |
| `test_real_generation_context_retention_preserves_control_and_read_traces` | Оба context packs сохраняют полный ID/body inventory реально подготовленных SQLite children, без потери или лишних дублей. |
| `test_completed_invocation_cannot_deliver_another_result_or_sink` | В ветви other_result второй самостоятельный вызов возвращает другой object; такой object должен быть отклонён существующим completion guard независимо от размера. Остальные три substitutions сохранены. |
| `test_unacknowledged_query_preserves_noncopyable_requirements` | Все три режима сохраняют весь authored ID/body inventory; прежние identity checks requirements, два dispatcher вызова и wrapper-versus-unwrapped сравнение остаются. |
| `test_real_lexical_public_retention_preserves_every_qualified_window` | Каждый из двух существующих reads имеет ровно один pure retention rerank по тому же qualified inventory. Ordinary context pack сохраняет те же полные ID/body pairs, что и acquired qualified windows; patch packet сохраняет прежние raw spans и hashes. |

Expected bodies берутся из исходных `p.chunks`, подготовленных fixture до вызова,
а в lexical случае — из реально приобретённых и независимо квалифицированных
source chunks. Число public sources не используется как единственный oracle.
Сохраняются проверки точного source substring, content SHA, char/line spans,
generation, source identity и исходных guards внутри текста.

В lexical тесте время ordinary rerank теперь сохраняется отдельно, затем список
очищается перед уже существующим patch-вызовом. У каждого вызова явно требуется
один rerank, а входной размер сравнивается с одним qualified inventory.
Старое суммарное ожидание одного события на два calls более не применяется.
Третий существующий возврат к ordinary docs по-прежнему обязан дать тот же payload.

## Сохранность побочных эффектов и граница проверки

Все сравнения dispatcher requests/results, SQL, source loads, source-file reads,
routing, selection decisions, consent и completion остаются. Новый read,
indexing, retrieval, projector или provider вызов не добавлен. Сравнения maps
и отдельное сохранение диагностического таймера выполняются на уже имеющихся данных.

Сохраняются и ранее успешно проходившие unresolved, stale, changed result/sink,
swapped sink, closed invocation, nested dropping delegation, finite catalog,
real-generation и no-copy guards. Новый runtime PASS не предполагается.
Текущий CI136 ещё проверяет прежний модуль; этот slice требует следующего
совместного прогона на опубликованном SHA.

## Manifest и review

- Path: `tests/test_action_packet_v4_found_window_retention.py`; mode `100644`.
- Base blob: `29e231b58288f2bd31d2ede4eddafd8be5179767`.
- Proposed blob: `8ccbc54def4e19299fed4e7e4b4a276da6150d49`.
- Proposed UTF-8 SHA-256: `d67975f0b474ecb978daa619765544d4dea8e41b1ca99fe83c607e5bfc76c818`.
- Десять обратных текстовых замен восстанавливают исходный файл побайтно.
- Source names и parametrization не менялись; diagnostic-label roster не меняется.
- Независимый review запрошен; локальные команды, Python imports/AST/pytest не запускались.
