# Source-bound search descriptions: bounded development

Разрешение владельца через parent относится только к этому opt-in эксперименту.
Исторические Qwen validation FAIL / v3 PRE-INFERENCE BLOCKED сохраняются.
Это local public Python API integration, не installed stdio, hybrid gate или Terra.

## Фиксированный контракт

- Шесть top-level Markdown Meridian; `modules/` не читается и не индексируется.
- Обычный lexical dispatcher; `with_vectors=False`; limit5, budget4096,
  expand none. Нет translation, E5, Qwen, classifier, model inference/downloads.
  Уточнение r3 до первого A/B: этот публичный API возвращает acquisition pool;
  limit/budget args фиксированы, но reported_not_applied. Сравниваются ВСЕ
  returned candidates под реальными acquisition ceilings, без top5/cropping.
  Это не final answer packet и не измерение уменьшения итогового контекста.
- `doc_scope=project`, `project_identity=step10-index-descriptions-meridian`,
  `source_class=project_file`, один явно заданный `resolved_version` snapshot.
  Значение: `meridian-source-sha256:` + SHA256 UTF8 канонического JSON карты
  `{path:source_sha256}`: `json.dumps(mapping, ensure_ascii=False, sort_keys=True,
  separators=(',', ':'))`. Это corpus identity, не опубликованная library version.
- Четыре неизменённых seen development вопроса и19 source-exact literal facts:
  `queries.json`, hash `ebdc87730508fe47d82cdcd978dff1ac768f443f0c20667417e09e0640f7346f`.
- Независимая source-only сессия подготовила English descriptions только из
  containing documents. `source-only-descriptions.json` не изменяется;
  hash `b9a690edba4f6186074ff4cccaddf5ed1acf1d439936e327e2c36fb8ad7f4b57`.
  Model `openai/gpt-6-astra#low`, harness generation, exact revision null.
  Provider usage недоступен; UTF8/4 — лишь инженерная оценка, не provider tokens.

## Artifact и ingestion

Optional `Document.metadata.experimental_search_descriptions_v1`:
`source_path`, `source_sha256`, `context_sha256`, `recipe`, `version`, `model`,
`model_revision` (строка либо null), `records`.
Record: integer `char_start/end`, `display_sha256`, непустая `description`,
`description_sha256`. Hashes — SHA256 UTF8, без префикса.
Context всегда полный containing document, поэтому оба source/context hashes
равны hash исходного документа. Списка моделей-разрешений нет.

Валидация отвергает неправильные types/ranges/fields, duplicate или unmatched
spans, устаревшие source/context/display/description hashes. Неполный список
records допустим в API; adapter development требует полного покрытия children.
Ошибка ValueError откатывает транзакцию; active generation сохраняется.

Baseline retrieval text и chunk boundaries вычисляются прежним кодом.
Description добавляется после baseline через newline только если <=512 UTF8
bytes и вместе с baseline <= прежнего hard_max. Иначе пропускается целиком:
`skipped_description_bytes` или `skipped_retrieval_budget`; успех `appended`.
Никаких cropping, re-chunking, замены prefix или source display.

Source-level metadata хранит полный artifact. Child хранит лишь matched binding
и status в `experimental_search_description_v1`; полный список records удаляется
из child metadata. Validator повторно проверяет source-level bindings и сам
восстанавливает ожидаемый retrieval text/status, не доверяя child description.
Validation не зависит от env-флага: старые поколения остаются проверяемыми.

## Исправление wiring r3: source-description-routing-v1

Первый исполнившийся integration дал1PASS/1FAIL: ingestion корректно записал
description, но clean-source admission игнорировал новое поле. Результат r2
сохранён. Parent разрешил включить только matched description со status=appended
в существующее description routing field рядом с project_doc_description.
SQL-expression одинаковый в admission и rank. Body statistics, body BM25,
title policy, веса routing0.125/content1.0 неизменны; без artifact используется
точно прежнее поле. Skipped descriptions не участвуют. chunk.text по-прежнему
source-exact; description metadata может быть видна Python-клиенту.
Это утверждённая correction recipe до first A/B, не retuning результатов.

## Embedding lifecycle (только code-path, без vector claims)

`list_sections_for_embedding()` уже выдаёт retrieval text и retrieval hash.
`sync_vector_store()` сравнивает retrieval hash для unchanged detection и
использует весь text в embedding cache identity. Поэтому изменение реально
добавленного description меняет fingerprint/cache input. Stable child/vector ID
остаётся source-bound; новый текст upsert заменяет значение этого ID. Public
agent создаёт отдельную collection на generation и проверяет witness до publish.
Пропущенное description не меняет embedding input — это намеренно.

## Публичная проверка / сбор evidence

`test_source_bound_search_descriptions_public_lifecycle` в существующем
`tests/test_contextual_indexing.py`: real ingest, lexical search, scoped selection,
точный display/hash/span, неизменные boundaries, оба whole-skip, stale rollback.
Другая project identity обеспечивает out-of-scope проверку. Никаких mocks.

`experiment.py prepare` делает ровно один public ingestion шести документов,
выгружает exact children через public store APIs, без queries и vectors.
`adapt` сопоставляет heading spans source-only artifact только exact children.
При несовпадении останавливается для parent; descriptions не размножаются.
`descriptions.json` — отдельный adapter bundle, исходный artifact не меняется.

`freeze` сохраняет hashes sources, queries, descriptions и всех Python product
files (включая прежний dirty worktree). `run` сверяет freeze перед двумя arms.
Каждый arm использует isolated SQLite/extracted/home. Raw packet сохраняется
до оценки. Fact считается только в raw returned candidate chunk.text соответствующего
source; description и metadata никогда не evidence. Internal candidate recall
не измеряется: наблюдается лишь публичная returned-acquisition boundary.

Проверяются source span/hash и scope/version каждого returned chunk; no-answer
означает пустой packet для заранее заданного no-answer question. Отдельно
сохраняются bytes source text, UTF8/4 estimate и bytes полного JSON packet.
Matched description metadata доступна Python-клиенту; это явно отмечается,
нельзя объявлять description невидимой клиенту. Projection refactor не входит.
Пустой no-answer packet при языковой границе не доказывает semantic success.
Runner model calls0 не включает отдельную annotation harness generation;
её provider costs/usage неизвестны.

## Исполнение

Нужен Python checkout environment `.venv/bin/python` с зависимостями DocAtlas;
`PYTHONPATH` указывает checkout. Установленный прежний wheel не содержит patch.
Команды/provenance, BEFORE, implementation.diff и freeze сохраняются до запуска.
Один prepare, один scoped integration run, один A/B run разрешены parent.
Setup ERROR сохраняется и требует нового направления перед повтором; quality
FAIL не меняет queries, source units, policy или критерии.
