# PR211: class carrier в mixed library snapshot

Статус: узкое исправление подготовлено для независимого review.
Новый обычный PR runtime ещё не выполнен; закрытие P1.5 и critical gate
не заявляется.

## Подтверждённый дефект на 107

Опубликованный HEAD: `321f36577577cb90a0422cee0de0b525b9cd658e`.
Merge checkout: `217d21017008240cf252e6b99e5c6e810a858a2a`;
tree: `9ea02d6b3dd7912b46000dc8174939ec0981e5d8`.

Автор прочитал фактический P1.5
[job 114101794391](https://github.com/Vanilla1999/DocAtlas/actions/runs/38014539398/job/114101794391).
Результат: 6/7 cases, 5/6 full facts, 6/6 self-controls.
Единственный failed case `two_claims_require_two_allowed_roles`:

- ProjectContext возвращает `ARCHITECTURE.md`, 37 символов,
  SHA-256 `7fdb4bd4ca083c8fac33df28f9a970516fc4a0549f5773ea5a2f90187fa69411`,
  с `delivery_decision.deliverable=True`.
- Unified содержит этот project source и exact Tenacity 8.2.3 source,
  65 символов, SHA-256
  `67f67da421e283f697af467f40a3916b970c77ad8014619fb72abb58393b14b8`;
  обе lanes имеют success, общий delivery=True.
- Финальный public packet содержит только библиотечный source.
  Отсутствует full fact из `ARCHITECTURE.md`; source/authority/preparation/state
  errors пусты. Observer counts: retrieval 1, validation 1.

В сохранённом библиотечном snapshot верхний `source_class` отсутствует,
а `metadata.source_class="library_doc"` и `metadata.doc_scope="library"`.
Это доказано отдельно от формы public DTO: `capture_source_binding`
копирует все присутствующие поля из `SNAPSHOT_LINEAGE_FIELDS`, где
`source_class` явно перечислен. Log показывает `lineage_fields_present`
без этого поля и исходный metadata carrier; `same_call_source_equal=True`.

Root отдельно прочитал JUnit reader job `114103727373`: новый независимый
mixed control падает на `critical_mixed_both_lanes`, получая только
`https://docs.clearpulse.test/2.7.1/reference.txt`; preceding
`critical_mixed_scope_producer` проходит.
Это самостоятельный fixture, не вопрос и не corpus P1.5.

## Производственный контракт

`_library_docs_service_part03.py`, blob
`07db6295be98e234c872f7370a9bcee37b0056f5`, создаёт canonical library candidate
с явными `source_class/library_doc` и `doc_scope/library` в metadata
(строки 702–750). Верхний candidate получает stable identity, hashes,
version и exactness, но эти два поля не поднимаются наверх.

`normalize_candidates` сохраняет исходный item в `EvidenceCandidate.original`.
Projector повторно проверяет canonical selection и передаёт именно этот carrier
в `_snapshot_entry` (blob `dd6795d83c8d863b12dd5e7d9ebe0712a19b2549`);
snapshot сохраняет raw original. Поэтому предыдущая проверка mixed helper
`source.get("source_class") == "library_doc"` отвергает легитимный текущий carrier.

Лог не содержит результата каждого более раннего helper return, поэтому
он не доказывает, что этот guard был первым исполненным отказом.
Однако для фактически сохранённого carrier этот guard неизбежно ложен;
его несовместимость с текущим producer доказана исходниками и actual snapshot.

## Узкое изменение

Private predicate читает только два объявленных class carrier: верхний
`source_class` и одноимённое поле metadata. Нужен хотя бы один literal
`"library_doc"`; все присутствующие значения должны быть точными строками
с этим значением. Отсутствие обоих, явный None, конфликт, неподдержанный тип
или malformed metadata запрещают добавление project context.

Проверка остаётся после действующих current request/producer-contract
и library snapshot guards. Raw snapshot, source hash, library selection,
exact version, consent и authority не меняются; class не выводится из URL,
body, doc scope или фактического ожидаемого результата.
Project admission, full quote, identity/module/path и final snapshot validation
остаются прежними. Никакие answer/edit/coverage права не добавляются.

## Существующий независимый control

Исправлены два неверных предположения oracle о месте хранения library class/scope.
Используется уже существующий независимый `lineage_values` с literal expected
`library_doc/library`; все присутствующие значения обязаны совпасть.
Проверки full bodies, SQL children, hashes, raw UTF-8 coordinates, exact version,
source identity, scope, public six fields и отсутствия answer/edit/coverage
сохраняются.

В тот же один pytest function добавлены 15 detached carrier iterations:
3 допустимых представления и 12 отсутствующих/конфликтных/None/malformed.
Используются реальные captured composer inputs; public quote и его hash
не переписываются. Перед вызовом проверяется исходная snapshot binding,
после — неизменность input и полный ожидаемый payload/snapshot.
Retrieval, SQLite и continuation IO в этих iterations явно запрещены.

Прежние 4 native calls, 28 detached request/source replays и отдельный
same-ID collision control сохранены. Эти 15 iterations — дополнительная
работа внутри одного function, не уменьшение числа исполнений.
Новых pytest имён нет; diagnostic node hash не меняется.
Этот slice не редактирует critical runner. Для базы 107 целевые 54/25
остаются pending до здорового baseline и intended-kill proof обычного CI.
Отдельный slice 108 добавляет два DQP3 mutants; совместная цель следующего
пакета — 54/27 pending. Ни один из этих результатов здесь не объявлен PASS.

## Manifest и проверка

| Файл | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| `docmancer/docs/application/mixed_context_projection.py` | `dcdf502c9d9b2a3788c1bfc41d377ad3cf1ade63` | `0007dbe25be2b629661fa82be4101858910f495d` | `100644` |
| `tests/docs/test_mixed_context_projection_contract.py` | `bd7435f507d9360030cb3c4c4411d2f485aefe90` | `99f4543092c3af0323bb511faba23c464fa95260` | `100644` |

Production inverse двух замен и test inverse пяти замен побайтно восстанавливают
base. Существующие три directed mutation anchors в helper по-прежнему уникальны;
остальные два находятся в неизменённых файлах. Локальные Python/import/AST/pytest,
новые workflows, зависимости, commits и refs не запускались и не менялись.
