# Восстановление scope и corpus runner без локального 3026969d

База: ef6a498046039f6e615f1928dd6539f046b327ab.
Ветка: next07-feasibility-audit. Пользователь разрешил восстановить нужный код
заново вместо ожидания недоступного локального commit. Старые результаты
3026969d не восстановлены, не присвоены новой версии и не объявлены проверенными.

## Что заменено

1. Scope-проводка: prepared() принимает scope/module_path. Discovery проходит
через штатный get_project_docs, который владеет преобразованием all в отсутствие
низкоуровневого doc_scope filter и разрешением module_path по текущему каталогу.
Нельзя просто послать all в query_project_docs: эта функция воспринимает значение
буквально. Повторный current-catalog/hash/lifecycle переход получает тот же запрос.
Ни ручного project_file -> project_doc, ни нормализации источника для PASS нет.

2. Диагностический runner: вместо двух вызовов реализован цикл всех 80 frozen
cases N/C, public-schema preflight, final handler snapshots для обоих arms,
existing audit/assessor, запись результата каждого arm до его оценки и таблицы IDs.
N остаётся штатным, C включает existing hooks с опциональным --compact-read.
Не используется исторический C/D projector replay вместо настоящего public call.

3. Failure accounting: локальный invalid сохраняется отдельно, quality FAIL не
обрывает оставшиеся случаи. Поломка изоляции или изменение frozen inputs прекращает
замер. Отсутствующие/неоценённые IDs не становятся пустым множеством потерь.
Assessor matches и source-valid retention показаны отдельно; needs_review сохраняется.
Исторический ledger 49 берётся только из опубликованного hash-checked extraction.
Historical partial retention без отдельного ledger не имитируется.

Read algorithm, ports, FTS/BM25 и first_fit неизменны. Последние empty/newline/
compact fixes сохранены. Production и source guards не менялись. Никакого нового
semantic parser, lexical threshold, rescue или настройки под N10 нет.

## Проверки

Локально: 120 PASS — 60 compact contract checks, 26 wiring checks,
21 новый scope contract и 13 checks диагностического учёта.
Это dependency-isolated tests: настоящие определения новых функций, но service,
source preparation и часть packing окружения заменены явными test doubles.
Тест полного цикла использует 80 синтетических cases и 160 fake calls; это НЕ
новый native replay и не измерение качества на frozen corpus.

В прежнем development wiring test обновлены только устаревшие ожидания, что
all/module_path обязательно запрещены, и spy signature. Их заменили явные
unsupported-lane controls; frozen product/security expectations не редактировались.

Добавлено 5 native scope scenarios: project, all, выбранный module, module_path
при project scope, отсутствующий module. Они используют реальные каталог,
индекс, MCP handler и audit. Здесь NOT_RUN: полный checkout/зависимости недоступны,
git ls-remote завершился Could not resolve host: github.com; mcp не установлен.
Ни 80 native pairs, ни новый P1/P2/P3, ни retention этой записью не выполнены.

## Запуск в полноценном checkout опубликованной версии

```sh
DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -q \
  v2plan/test_next07_compact_delivery.py \
  v2plan/test_next07_grounded_public_wiring.py \
  v2plan/test_next07_scope_rebuild.py \
  v2plan/test_next07_diagnostic_runner.py \
  v2plan/test_next07_scope_native.py

# Создай OUT через mktemp; подкаталоги target и corpus-replay ещё не существуют.
DOCATLAS_OFFLINE=1 .venv/bin/python -m v2plan.next07_grounded_final_run \
  --compact-read --out "$OUT/target"
DOCATLAS_OFFLINE=1 .venv/bin/python -m v2plan.next07_diagnostic_scope \
  --compact-read --out "$OUT/corpus-replay"
```

Native smoke failures нельзя спрятать за большим числом contract PASS.
Corpus exit 0 означает только CORPUS_DIAGNOSTICS_COMPLETE: все пары валидно
исполнены и оценены, не «качество прошло». Exit 2 означает PARTIAL/invalid.
Raw captures/assessments/trace: cases/<id>/{N,C}/. ID lists и review queue:
result.json. Строки observed_claim_rows связывают witness rows с фактически
записанными packing events; они не выдают догадку за единственную причину потери.
Остальные public controls и historical partial retention этим runner не закрываются.

## Итог

Недоступный 3026969d больше не нужен для запуска восстановленного кода.
Сохрани его локально для истории; он не удалён и не заменён в рабочей копии.
Новый native smoke и corpus replay: NOT_RUN. N10: REJECTED_N10_UNCHANGED.
Полный HARNESS_READY, качество и rollout не объявляются. Старые artifact files
не менялись. Коммиты разделяют scope wiring и corpus diagnostics.
