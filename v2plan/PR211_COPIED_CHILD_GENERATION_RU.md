# PR #211: поколение metadata при переносе неизменного child

Статус: узкий producer fix и усиление существующего regression control. Runtime нового slice ещё не выполнен.
Base: `1c6c2c8454cdd6fe797fe80e85f3b651aef01a0a`.

## Фактическая причина

[Actual P15 run](https://github.com/Vanilla1999/DocAtlas/actions/runs/38003248308/job/114066060666)
на merge checkout `64caa3caf213a6a67d44c92546660ef1ced23d87`: **4/7 cases**, **2/6 complete facts**, **6/6 oracle controls**.
После исправления finite library filter binding библиотечный факт найден и полностью доставлен.
Source-integrity проверка сохраняет FAIL: committed child и возвращённый источник имеют разные generation IDs при совпадающих stable ID, parent, source/body hashes и spans.

Для dependency case:
- active committed SQL generation: `gen-357f2bd211af4df49927529d5d6c0dd7`;
- возвращённая metadata generation: `gen-47d0e92bb3564d3294e59d426806a89b`;
- stable child: `child-03a87a6ec55178e338a0aa80cbe92da9ae780254`.

Source-derived механизм:
1. Fixture явно подготавливает docs URL, затем robots URL; каждый вход проходит настоящий отдельный `agent.add`.
2. Второй add создаёт новое поколение и копирует неизменный docs child.
3. `_insert_retrieval_child_copy` записывает новое SQL `generation_id`, но раньше переносил JSON metadata со старым значением.
4. Query и hydration возвращают сохранённый JSON. `read_stored_children` читает SQL generation, поэтому строгий oracle обнаруживает расхождение.
5. `index_state` только хеширует состояние; совпадение before/after не указывает на read-time rebuild.

New-child путь уже присваивает canonical generation. Дефект локализован только в copy-path.
Общий `index_health()` сверяет promoted filter columns, в которые generation не входит; одного health assertion недостаточно.

## Изменение

Перед serialization скопированной metadata присваивается target generation из уже существующего аргумента producer.
Stable/hydration/vector/parent/source IDs, hashes, тексты, spans, фильтры и immutable старое поколение сохраняются.
Query/hydration, общий validator, схемы и read-only policy не меняются; существующие старые DB при чтении не переписываются.

Существующий `test_incremental_generation_canonicalizes_metadata_from_promoted_columns` сохраняет оба исходных add, тексты и deliberate authority forgery.
Он дополнительно проверяет:
- SQL generation и JSON generation скопированного child равны новому active generation;
- все прочие SQL поля, кроме нового row ID и metadata JSON, совпадают с сохранённым child;
- JSON изменился только на canonical authority и generation;
- настоящее lexical query и hydration возвращают то же поколение, source bytes, hashes, identity и spans;
- старые rows остаются побайтно прежними, включая deliberately forged authority metadata.

Все **21 test names** файла сохранены. Другие test functions и parameters не меняются.
Обратная замена одного function body восстанавливает base test file побайтно.

## Manifest

Все mode `100644`.

| Path | Base blob | Proposed blob |
| --- | --- | --- |
| docmancer/core/_sqlite_store_part02.py | 9e851df34c77779c4495435d098fab68afe14059 | 483b72a3aaf4b85c12260a637c92b9ea81aa1ffd |
| tests/test_parent_child_index.py | 168884f21465894c3c84c1ac083435d194c1a3a5 | a4d6ed776bbe3ef70320329f37d1aa750d70544f |

Отдельная P15 capture/oracle migration сохраняет top-level и nested evidence; этот producer fix не меняет oracle или gold.
Frozen **7 questions / 13 candidates / 6 full facts / 2 negatives** здесь не затрагиваются.
Решения по document-statement/mixed qualification и полный quality PASS остаются отдельными задачами.

## Acceptance

Независимый review production diff, неизменности прочих test functions и actual P15 generation evidence выполнен root: APPROVE.
Остаются actual existing incremental selector, основной core и P15 на конечном опубликованном SHA.
Новый runtime, syntax check или P15 PASS не заявлены. Локальные imports/pytest/subprocesses не запускались.
