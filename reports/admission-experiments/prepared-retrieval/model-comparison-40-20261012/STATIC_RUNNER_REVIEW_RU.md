# Независимый review runner и offline scorer до исполнения

Дата: 2026-10-12. Проверены `eval/prepared_model_comparison40/run.py` и
`evaluate.py`. Reviewer не писал эти файлы, не запускал продукт, модель или
тесты и не менял corpus/oracle. Все замечания ниже высказаны до первой новой
индексации и inference; исправления выполнены авторами до заморозки.

## Замечания, исправленные до запуска

1. Первоначальный runner проверял состояние SQLite и документов только после
   пары. Теперь полное логическое содержимое всех таблиц и hashes всех project
   files проверяются до и после каждого arm против исходного состояния.
   Изменение останавливает работу до следующего вызова. Эти проверки находятся
   вне измеряемого public query time, а их стоимость входит в общий run wall.
2. Первоначально две ошибки без selection receipts могли называться
   `not_reached_both`; любое число receipts не отвергалось. Теперь разрешена
   ровно одна receipt в каждом reached arm либо ноль в обоих при успешных
   `docs_context` результатах и полном observer. Ошибки остаются `unpaired`.
3. Завершение workload отделено от действительной валидности публичной границы.
   80 начатых попыток с отсутствующими результатами не считаются полноценным
   успешным прогоном. Сохраняются attempted, returned, comparable и reached counts.
4. Копирование model-load receipt в ledger содержало конфликтующие kwargs
   `operation`/`status`; receipt теперь вложена отдельным полем. Hash большого
   model asset считается потоком, без загрузки всего файла ради hash в память.
5. Offline scorer теперь требует metadata status строго `returned`, проверяет
   точные wire bytes/hash и UTF-8 proxy, отдельный final-cap verdict, а для
   negative также `context_available=False`. Проверяется `unversioned` fixture
   binding, все frozen file hashes и completeness диагностических receipts.
6. Переходы gain/loss по сопоставимым парам отделены от необусловленных raw
   outcome transitions. Сопоставимость должна учитывать одинаковые полные
   pool/universe/exclusions, валидную cardinality/status публичной границы,
   source identity и сохранённое read-only состояние. Некорректная пара остаётся
   в отчёте с причиной исключения из causal comparison.

Эти изменения усиливают исполнение заранее согласованного публичного контракта.
Ни вопрос, ни required source span, ни k=2, ни общий cap=12000 после результатов
не менялись: на момент review результатов ещё нет.

## Проверенные границы runner

- Весь исторический V40: пять реальных изолированных preparations и 40×2
  публичных `get_docs_context`; нет дополнительного capture read или generator.
- Общие pinned документы и generation в каждой паре; prepared flag устанавливается
  внутри `isolated_service` до indexing. Наличие manifest проверяется после
  реального commit исходников. Corpus/oracle не передаются модели.
- Режимы чередуются по заранее заданному индексу; общий admission и оба budget
  неизменны. Модель resident, cold preload отдельно, без readiness forwards.
- Точный публичный payload сохраняется с исходным JSON порядком отдельно от
  trace/selection receipts. Никакие private diagnostics не добавляются в DTO.
- Failure ledger начинается перед операцией и сохраняется синхронно, повторы
  автоматически не выполняются. Прерванный или ошибочный вызов остаётся видимым.
- Timing охватывает реальный public call, включая inline scoring, trace и
  observer copies. Cold import/asset verification/load и общий run wall
  представлены отдельно. Shared process RSS не является сравнением памяти
  отдельного процесса без модели с отдельным процессом Mini.

## Проверенные границы offline scorer

Scorer использует стандартную библиотеку и сохранённые исходники/артефакты;
DocAtlas, модели и retrieval не импортируются и не повторяются. Gold состоит
из неизменных исторических line ranges; trimmed только внешние пробелы.
Проверяется объединение точных final snippet spans по нужному исходному path.
При неоднозначном размещении повторяющегося текста используется гарантированное
пересечение возможных положений, а не удобное первое совпадение.

Подлинность проверяется по pinned raw SHA, сохранённым prepare и generation-source
hashes, project/scope/version и snippets в объявленных строках. Public projection
fingerprint проверяется на форму; его независимый пересчёт не заявляется.
Continuation locators проверяются по доступным полям, но не dereference.

Whole-wire bytes и UTF-8/4 scorer пересчитывает независимо. o200k_base берётся из
сохранённого измерения runner; это явно не независимый повтор tokenizer и не
billing. Результат охватывает контекст перед генератором. Semantic relevance,
недостающие условия и достаточность требуют отдельного ручного review и не
переписывают strict gold verdicts.

## Решение

После внесения отмеченных проверок оснований блокировать один замороженный
ограниченный запуск не найдено. Static review не является runtime PASS.
Следующее доказательство — фактические 80 public payload, same-pool/state
receipts, число реально исполненных model forwards и независимая оценка
полученных контекстов. Корпус исторически открыт; обобщение на продукт целиком
и качество ответов генератора этим опытом не доказываются.
