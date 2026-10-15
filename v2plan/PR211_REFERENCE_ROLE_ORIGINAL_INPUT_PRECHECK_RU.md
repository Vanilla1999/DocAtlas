# PR211: исходные reference inputs без вывода ролей из прозы

## Результат этого slice

Подготовлен precheck для **19** устаревших ожиданий из `test_query_reference_roles.py`. Ни один исходный тест пока не удалён. Существующая функция `test_literal_mentions_keep_sha_unicode_offsets_and_occurrences` теперь выполняет все 19 исходных вопросов с независимым текущим oracle; прежний здоровый Unicode/path/duplicate контроль остаётся первым.

Это сокращение числа отдельных pytest cases после будущего подтверждённого retirement, а не сокращение 19 вызовов parser. Предварительная идея с тремя representatives отклонена: existing reference92 не содержит остальных точных исходных вопросов. В финальном варианте каждый из 19 сохранён и исполняется. Неисполняемый архив и старые FAIL сами по себе не служат доказательством замены.

База audited sources: `7b56e7b61ff28024349ae13d8e60a591788b83cf`, tree `0efae221bcb7a65e1cf18a3e6525f0f9146c89e0`. Runner использует отдельно согласованную reviewed V2-базу `8b9e6f1e73a6fd855675935ccb6d1da043e3f72e`. В manifest сохранены точные base guards для обеих изменяемых файлов.

## Действующий контракт

В `query_reference_binding.py` blob `06215d1e4deaa4c56a2c0afac135bd2f2a29a858`, строки 61–93, `query_mentions` извлекает синтаксические literal occurrences; слова «file», «constant», «library» и их русские аналоги не присваивают source/symbol/subject role. Оригинальные spelling, координаты и SHA вопроса сохраняются. Это соответствует принятому ADR0003 и завершённому удалению NL dictionaries; их точные пути/SHA находятся в crosswalk.

Oracle различает три ситуации:

- Три исходных `ARGON` records требуют один точный occurrence `unresolved`, `explicit=False`, с собственными исходными span и mention ID.
- Четырнадцать unquoted plain records допускают отсутствие occurrence либо ровно один собственный `unresolved`, `explicit=False`. Это не разрешает дополнительные слова/спаны/roles. Действующий technical extractor `query_terms.py` blob `8d047ff87066d43416ae5102038237605ada0a28` не обязан создавать bare Cyrillic occurrence; тест не выдумывает его. Полное опустошение extractor не пройдёт исходный healthy контроль и обязательные ARGON/quoted records.
- Два исходных quoted `ArgonGuide` требуют один точный `symbol_identity`, `explicit=True`, независимо от prose «in the file».

`resolve_references` — отдельная граница, строки 229–286 того же source. Два дополнительных чистых вызова на тех же quoted questions проверяют настоящий complete in-memory catalog `docs/ArgonGuide.md`: backtick сохраняет symbol identity без `source_ids`; double quote может связаться с этим разрешённым catalog member. Оба сохраняют исходный question, scope и mention. Синтаксическое `resolved` не объявляется доказательством body fact или answer authority.

Значения нового oracle взяты из этого контракта, не из выполнения старых tests или подгонки фактического return. Frozen JSON содержит исходные параметры, все 19 raw questions, их UTF-8 SHA-256, буквальные span и ожидаемую границу. Историческая роль сохранена как данные и не используется для присвоения текущего ожидания.

## Полная карта 64 исходных cases

Числа получены статически из literal decorators; hashes нормализованных node names независимо совпали с существующими diagnostic label shards. Это не новый collect/runtime receipt.

| Функция | Исходных cases | Кандидат | Остаются | Решение |
| --- | ---: | ---: | ---: | --- |
| `test_context_not_case_assigns_role` | 12 | 12 | 0 | кандидат; только после own proof |
| `test_same_spelling_has_distinct_source_and_symbol_occurrences` | 1 | 0 | 1 | сохранить; смешанный контракт разобрать отдельно |
| `test_russian_roles_preserve_unicode_offsets` | 5 | 5 | 0 | кандидат; только после own proof |
| `test_quotes_preserve_contextual_role` | 4 | 2 | 2 | частичный кандидат; две constant rows сохранить |
| `test_longest_span_does_not_create_substring_obligations` | 4 | 0 | 4 | сохранить |
| `test_bare_uppercase_is_not_automatically_subject` | 1 | 0 | 1 | сохранить |
| `test_query_and_offsets_identify_occurrence` | 1 | 0 | 1 | сохранить |
| `test_lone_quoted_filename_keeps_strict_identity` | 1 | 0 | 1 | сохранить; смешанный контракт разобрать отдельно |
| `test_descriptive_nouns_do_not_invent_source_or_subject` | 1 | 0 | 1 | сохранить |
| `test_slash_comparison_is_not_a_source_path` | 1 | 0 | 1 | сохранить |
| `test_weak_source_hypothesis_does_not_invent_a_lowercase_exact_term` | 1 | 0 | 1 | сохранить; смешанный контракт разобрать отдельно |
| `test_anaphoric_default_does_not_invent_a_named_subject` | 5 | 0 | 5 | сохранить |
| `test_repeated_parse_reuses_immutable_mentions_not_scope_resolution` | 1 | 0 | 1 | сохранить; смешанный контракт разобрать отдельно |
| `test_code_paths_are_identities_not_document_locators_without_source_context` | 2 | 0 | 2 | сохранить |
| `test_locator_rename_preserves_command_without_body_change` | 16 | 0 | 16 | сохранить native quality |
| `test_command_substitution_is_preserved` | 3 | 0 | 3 | сохранить native quality |
| `test_exact_case_collision_keeps_document_identity` | 2 | 0 | 2 | сохранить native quality |
| `test_navigation_only_source_does_not_prove_a_fact` | 1 | 0 | 1 | сохранить native guard |
| `test_other_project_index_does_not_invalidate_selected_source` | 1 | 0 | 1 | сохранить native guard |
| `test_forged_heading_trace_does_not_authorize_sibling` | 1 | 0 | 1 | сохранить native guard |

Итого: 20 функций / 64 cases, из них 19 кандидатов и 45 сохраняемых cases. Четыре mixed tests сохраняют meaningful occurrence, strict filename, no invented noun и cache/scope obligations; их нельзя удалить вместе с classifier ожиданиями.

Все 24 `reference_behavior_matrix` cases сохраняются. Их assertions защищают доставку реальных command facts, подстановку команд, case-sensitive source identity, navigation-only отказ, project isolation и запрет forged sibling authority. Отсутствие final source здесь не доказывает устаревание задачи. Возможная raw-LF fixture несовместимость исправляется отдельным helper slice и также не означает 24 quality PASS.

## Работа и стоимость

- В existing node сохранён один начальный `query_mentions` вызов; добавлены **19 прямых** вызовов на всех исходных вопросах.
- Добавлены **2** in-memory `resolve_references` вызова на уже разобранных quoted questions. Они используют настоящий resolver и ту же literal identity; native service/index/API запросов нет.
- Читаются два frozen source archive и один JSON с inputs. Старые Python modules не импортируются и не исполняются для получения gold.
- Новых test functions или parametrized cases нет. Existing reference92 остаётся 28 функций / 92 cases. В normal critical roster добавлен один ранее существующий node.
- Старые 19 cases пока collected, поэтому precheck временно добавляет работу. После отдельного retirement число pytest items уменьшится на 19, но эти 19 authored query evaluations останутся в компактном oracle. Ускорение wall-clock не измерялось.
- Matrix остаётся с 24 public reads, 25 indexing calls, 24 isolated service contexts и 27 document submissions. Эти операции не спрятаны внутри нового wrapper.

Whole-live file pins и AST preservation checker не добавлены. Frozen archives закрепляют исторические inputs; будущие независимые изменения живых helpers/tests не блокируются этим oracle. При последующем retirement source preservation проверяется конкретным diff/inverse, retained ranges, owning diagnostic label и peer review.

## Адресные production faults

Оба faults меняют текущий `query_mentions`, имеют один точный source anchor и используют существующий import-owner `docmancer.docs.domain.query_reference_binding` в harness. Нового production module/импорта в harness нет.

| Fault | Первый intended input | Именованный guard | Expected outcome |
| --- | ---: | --- | --- |
| `reference_nl_context_cannot_promote_bare_locator` | 0 | `critical_reference_nl_context_keeps_bare_unresolved` | 1 FAIL, 0 ERROR, 0 SKIP |
| `reference_nl_context_cannot_promote_quoted_stem` | 17 | `critical_reference_nl_context_keeps_quoted_symbol` | 1 FAIL, 0 ERROR, 0 SKIP |

Первый возвращает source promotion для bare technical spelling после «in the file». Второй ошибочно считает quoted stem path из-за тех же окружающих слов. Исходный healthy Unicode/path/duplicate контроль и все предшествующие replay rows остаются корректны до собственного intended guard. Конструкторы и типы возвращаемых объектов остаются допустимыми; ошибка не должна объясняться import/constructor/collection failure.

- Общий production source SHA-256: `0bdf65939526fd19ecc239ce3a3ee67bdaf9d067e184798f0b8f9f9b13ef528b`.
- После bare fault: `cc79163e504c990478576016e947cbfbc7151b8eb89ceecb36e8e86de7bb2d35`.
- После quoted fault: `bbf519aa48fd224405f25fce03b4809346ef5eb2fc58d9feeb920f03b878510c`.
- Existing 41 mutant blocks и executor сохранены побайтно.
- Runner: 979 → **998 physical lines**, ограничение 1000 не изменено. Новые 19 строк — один selector и два явных девятистрочных `Mutant` блока.
- Следующий normal target: **62 baseline cases / 43 intended mutants**. Это ожидаемый roster, не полученный PASS.

Исторические «104 literal receipts» относятся к двум baseline children и 51 faults в двух режимах для другого compiler/literal family. Они не заменяют own reference92 или новый replay proof.

## Архивы, consumers и hashes

Оба полных исходных modules сохранены как `.py.txt` с теми же Git blobs. Crosswalk содержит все 20 function mappings, 19 raw input records, source hashes, две mutation recipes и pending proof.

Consumer inventory фиксирует точный audited tree и 1291 прочитанный source/config path, 0 read errors. Буквальных external imports/selectors для двух target modules и выбранных трёх функций не найдено; shared `_reference_binding_fixtures` имеет 14 code consumers, все сохраняются. Проверены обе owning diagnostic label shards. Это bounded literal-reference audit, не заявление о произвольно вычисляемых import names.

- Full source roles SHA-256: `8109bda521861fcc4be5c3be57c42b9a4b63dc38eafbb088247fe60525082aa6`.
- Full source matrix SHA-256: `1c760ae7be2dffeab5b71a1ccdb30163fc2bb465045048bf235a6b2f227bebcf`.
- Frozen 19-input digest: `deef6debbad224f9f3bf0d146654f3b703c3748fc82345058697bd0f91373cf8`.
- Full 20-function mapping digest: `5fed163b62cd56b36f9479b37200e2f26a9b50d0667c6ae291f42c806f3ba2e2`.
- 1291 path/SHA inventory digest: `bdbe7e449c2f542d5080648987dd6464c447c626912c66da2f1205d3fc3c00f6`.
- Proposed existing test source SHA-256: `c9f6a09e2932e02ff3b1cb266052c30aab542b1ab61d831e602bf8022d317f77`.
- Proposed runner SHA-256: `200b27626929abacac25b8ae952014aed331581d7a5318a9a1cb35c6f76b5e27`.

## Manifest и стадия принятия

| Path | Mode | Base blob | Proposed blob |
| --- | --- | --- | --- |
| `tests/test_dictionary_exit_reference_ranking.py` | `100644` | `27adc50fa21225bb0faa523012efb5d63b6abc37` | `49dfcec80c43b02820052e4ffefe95c3d44c7b68` |
| `scripts/run_critical_mutation_gate.py` | `100755` | `8b9e6f1e73a6fd855675935ccb6d1da043e3f72e` | `15413c51f495d09ce11ebd1f48f2b1ea65603fa2` |
| `eval/task_level/contract_history/query_reference_roles.py.txt` | `100644` | new | `2b71d1712b19e33a198d4c209549260f24738b8e` |
| `eval/task_level/contract_history/reference_behavior_matrix.py.txt` | `100644` | new | `84f8fdc218fd2ac4fb2ec0962bf698cb1d100012` |
| `eval/task_level/contract_history/reference_role_inputs.json` | `100644` | new | `fcb687783ac9715af179dd947c91427bb43cc379` |
| `eval/task_level/contract_history/reference_role_consumers.json` | `100644` | new | `431530e745fddb1104f27231d3d5d77a753c61eb` |
| `v2plan/PR211_REFERENCE_ROLE_ORIGINAL_INPUT_PRECHECK_RU.md` | `100644` | new | этот документ |

Все шесть code/data blobs перечитаны из GitHub, roundtrip exact. Удаление одного нового блока test body восстанавливает base `27adc50f` побайтно; удаление одного selector, count и двух appended mutants восстанавливает runner `8b9e6f1e` побайтно. 28 existing test names, их decorators и diagnostic node hash не изменены. Target modules, их imports/helpers/parameters и все 64 cases остаются live.

Локальных runtime/import/pytest прогонов не было. Independent static review и actual совместный CI ещё нужны. До удаления 19 необходимо получить normal62 baseline с 0F/0E/0S, все43 intended kills и отдельные реальные receipts двух новых faults с правильными node/guard/1F/0E/0S; прочитать current broader reference92 result и проверить source/selector сохранность. Нового PASS и выполненного retirement этот документ не заявляет.
