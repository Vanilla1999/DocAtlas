# PR #211: независимый review catalog slice

Дата: 2026-10-08. Reviewer: отдельный acceptance-audit агент, не автор source,
schema matrix или companion migrations. Полное обоснование изменений находится в
[отчёте автора](PR211_CATALOG_REVIEW_RU.md).

## Verdict

**APPROVE — статический review code/schema и companion tests**, после исправления
четырёх замечаний ниже. В финальном diff не найдено ослабления schema admission,
до-service validation или сохранённого смысла public guidance.

**Footprint acceptance открыт: 7066 > 6144 bytes, превышение 922 bytes.**
Output schema — 860 < 1000 bytes. Предложение 7168 bytes этим review не одобрено.
Действующий `test_default_public_catalog_meets_task35_hard_and_target_budgets`
не изменён и не пропускается. Это code-review approval, не merge/release approval.

## Проверенный scope и закрытые findings

Проверены source diff от `21fe472d983f394130849d6fd4e582043d58e9ba`, frozen fixture,
новый equivalence matrix, общий guidance helper, compact/registration/dictionary
companions, оба host-scope call sites и новый diagnostic shard. Прочитаны реальные
producers: `_docs_server_shared.py`, `_docs_server_part01.py`, schema/surface types,
`prefetch_tools.py`, member transaction и storage policy.

1. **with_vectors:** удаление свойства расширяло standalone admission неверного
   типа в открытой non-sync schema, хотя dispatcher всё равно отказал бы до I/O.
   Свойство восстановлено буквально: nullable boolean и default=false. Matrix
   проверяет все 12 actions; runtime rejection не подменяет schema equivalence.
2. **До-service evidence:** одного `validation_error` было недостаточно: такой
   label возможен и после handler dispatch. Финальный тест использует реальный
   dispatcher/current schemas и counters на resolver, service selection, handler.
   Положительный docs_status control достигает всех трёх, invalid inputs обязаны
   оставить нули. Monkeypatch направлен в defining shard, не в re-export facade.
3. **Status provenance:** финальная prose снова требует explicit status requests
   либо returned recommended_next_action/job_id; read-only/no discovery сохранены.
4. **Subject binding после relocation:** helper больше не принимает произвольный
   субъект перед `always implies module scope` или `current project: omit`.
   Проверка привязана к field description либо явному имени module_path/version;
   exact/historical version разрешена только explicit, не inferred.

Остальные сокращения ограничены redundant string enum/const types, пятью
pattern-implied minLength и равносильными if/then/else. Hash/generation maxLength
оставлены против terminal newline; nullable и JSON bool-vs-number различия
сохранены. Normalizer проверяет только эти преобразования, не удаляет произвольные
validation keywords. Нет новых refs/loader, generic schema или server-only обхода.

Исторические RAW/input/output hashes базы 8346f6d6 в dictionary companion сохранены.
Current input сначала сравнивается с независимо hash-verified 21fe fixture, затем
baseline используется для прежнего reconstruction; advanced сравнивается после
той же ограниченной нормализации. Guidance сохраняет explicit-only lookups, scope,
current binding, data-only trust, отсутствие edit authority и lifecycle guards.
Существующие test nodes не удалены и не переименованы.

## Evidence и ограничения

Reviewer выполнил source/diff review, `wc -c`, `sha256sum`, проверку diagnostic
node hash и `git diff --check` без замечаний. Проверены saved catalog artifacts:
7602 bytes baseline и 7066 bytes candidate. Их AST extraction/normalization выполнены
автором; это не независимый runtime build каталога.

Новый module имеет пять nodes. Reviewer независимо проверил hash их отсортированных
base IDs по существующему inventory алгоритму:
`234d14a2ca37ed6a1cce1f4a86b283fa8951bf6e73b55112194d2e7eb3011468`.
Четыре nodes помечены schema, один — behavioral; старый inventory не обходится.

Автор создал 417 boundary cases; это **не 417 PASS**. Координатор отдельно сообщил
isolated stdlib helper positives/negative controls, включая три финальные подмены
subject/explicit-version. Reviewer проверил соответствующую логику по source.
**Pytest, JSON Schema runtime, MCP stdio, CI и clients reviewer не запускал.**
Project imports, downloads, subprocess runtime и user indexes не использовались.

Открыты footprint decision/дальнейшее сокращение, joint run на конечном SHA,
required CI/downstream/platform и необходимые installed/client проверки. Frozen
retrieval criteria и отложенный retrieval этим slice не менялись.

## Final reviewed SHA256

Это hashes содержимого, не tested commit SHA.

| Файл/артефакт | SHA256 |
|---|---|
| `_docs_server_tool_data.py` | `04bc8f230f6f751f886aad19e8b57f95840626648ce80fbf0f45a5fe4bedc09e` |
| `test_pr211_catalog_equivalence.py` | `3475753adf1f043b13c9d4b325fc4341bd6bab6129d2de502d88cf6446e78473` |
| Frozen catalog fixture | `ad63f367601a18fe04ec715800be2a935a7496c16beb71df4d1818d258bc06db` |
| Current canonical catalog | `229b90fb1a58e4255cd5926f726f2d28b6171232491f91b1341e417bea51f397` |
| `_scope_guidance_contract.py` | `18021468b93c0b0e00d14074ec6b2d96d4b038fb6a5088d21936a281f882190f` |
| `test_compact_docs_surface.py` | `ec82c66b3d2693d04322c9b2d0bcb883566ccd4bb5018eee4d9bef697be38065` |
| `test_mcp_docs_tools_registration.py` | `9dc2e26e599c481215a5ebc49e7a4f5429c151ceccabb5c53419614fdc28d6ff` |
| `test_dictionary_exit_delivered_surfaces.py` | `354f15d5ea9c70ec274025007bf7b8daac49d77bf60280b611ff3f6f9da204a1` |
| `diagnostic_labels.pr211_catalog_equivalence.json` | `ecc950afeefe6f2764976694c7b86dcec140d5250a3618ff12a93ad89a7aa27a` |
