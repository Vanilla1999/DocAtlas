# M2: ограниченный разбор серьёзных дефектов

## Исправлено без ослабления guards

1. MCP catalog был 6455 bytes при hard budget 6144. Descriptions сокращены,
   runtime lookup guidance сохраняет original question unchanged, identifiers,
   versions, negation/conditions/comparison sides, запрет guessed sources и
   expected answers. Текущий каталог: 6115 bytes; hard-budget assertion сохранён.
2. `context_tools.py` вырос до 1022 lines при hard budget 1000. Typed intent
   normalization выделена в `context_intents.py`, error reason codes/defaults
   и fail-closed mutation behavior сохранены. Size-policy tests проходят.
3. Historical pre-M2 test archives переведены в `.txt`: это не executable
   legacy path и не acceptance suite; историческое содержимое сохранено.

`m2_serious_fixes.log`: **144 passed**, включая size/catalog, schema,
patch/read routing, Unicode/lifecycle/defaults и host guidance controls.
`m2_stable_runtime_controls.log`: **33 passed**. Runtime freeze tests сперва
отказали из-за intentional deleted files в unstaged index. Удаления и новый
helper внесены в index; safety/preflight guard не изменялся. Это не namespace
limitation и не baseline defect. Commit пока не создан.

## Сравнение с checkpoint, не с исходным rollout baseline

Изолированный worktree `/tmp/opencode/docatlas-m2-serious-baseline`, commit
`5a732198`. Полный `tests/docs`: **3461 passed / 50 failed**,
`m2_full_checkpoint_baseline.log`. Этот checkpoint уже содержит ранние slices
M2, поэтому он не доказывает absence regressions относительно acf9a277.

Четыре 256-token coverage failures воспроизведены и на checkpoint без нового
planner. `httpx-07` на checkpoint проходит, в current падает: это настоящая
новая потеря documented fact, не legacy-only expectation.

Последний стабильный current run, без параллельного редактирования кода:
`m2_serious_stable_docs.log`: **3341 passed / 110 failed**, 170.03 s.
По test IDs: 26 failures общие с checkpoint, 84 current-only; 24 checkpoint
failures current больше не имеет. Разный набор test cases после retirement
не позволяет считать число PASS метрикой retrieval quality.

Current-only failures не объявлены автоматически obsolete: в них есть
fixture dependencies, отменённые generated semantics, actual source/delivery
controls. Восемь namespace failures остаются непроверенными environmental
cases. Checkpoint-common failure не означает, что его можно удалить.

## Решение о закрытии

Критические M2 budgets/default routing исправлены, но **M2 не закрыт**:
documented fact loss `httpx-07` сохраняется и downstream lexical gate требует
отдельного решения в границе M4. Изменение universal admission до M3 или
закрытие M2 только по focused PASS было бы изменением согласованного gate.
Оставшиеся source/delivery assertions не ослаблены, не xfail и не удалены.
M3/M4 не начаты; push/merge не выполнены.
