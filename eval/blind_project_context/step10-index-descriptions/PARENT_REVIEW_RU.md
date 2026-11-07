# Итоговое parent review: эксперимент выполнен, улучшение не подтверждено

Дата: 2026-11-07. Анализ и решения выполнял parent, реализацию и ограниченные
прогоны — Astra Low. Отдельная Astra Low сессия подготовила21пояснение по шести
исходникам без доступа к вопросам/labels. Это единое итоговое review кода,
исходных материалов и runtime evidence; parent не повторял продуктовые прогоны.

## Вердикт

**Принимается как opt-in development implementation и воспроизводимый
отрицательный результат. Оснований включать по умолчанию или объявлять
улучшение retrieval/сокращение контекста нет.**

Покрытие обязательных фактов в возвращённых кандидатах:10/19 →10/19.
Полнота не достигнута, объём вырос. Это не новый Qwen результат: здесь другой
публичный acquisition-путь, без Qwen/embeddings/Terra. Прежние FAIL/BLOCKED
сохраняют собственную границу доказательства.

## Что независимо проверено

- Вопросы неизменны;19literal facts сверены с исходными документами.
  Исходная часть review: `PARENT_SOURCE_AUDIT_RU.md`.
- Все440 code hashes frozen manifest совпали с текущими bytes; source,
  queries, original descriptions и adapter bundle hashes совпали.
- Runtime frozen-inputs равны pre-run manifest.
- Семь секций `implementation.r3.diff` независимо восстановлены из BEFORE
  и текущих файлов побайтно. BEFORE учитывает предшествующие dirty changes.
- Прочитаны новые validator/append/binding, оба storage seams, admission SQL,
  evaluator и public integration scenario. При отсутствии artifact используется
  прежнее поле routing; source display не заменяется пояснением. Source-level
  artifact проверяется повторно, child binding сверяется с ним.
- Только status=appended участвует в существующем routing field. Body BM25,
  его статистика и численные веса не изменены. Embedding cache использует
  retrieval text/hash; это code-path review, не выполненный vector acceptance.
- Integration stdout:2passed, stderr пуст; прежние collection ERROR и1PASS/1FAIL
  сохранены. Сценарий действительно обнаружил пропущенный admission wiring,
  затем прошёл после исправления без изменения теста. Новый unit suite не создан.
- Все восемь raw A/B packets пересчитаны отдельным parent script без импорта
  production scorer/evaluator: проверены literal facts только в source text,
  точные spans/hash/scope/version, число candidates и размеры файлов.
- Scoped `git diff --check` прошёл. Повторных inference/A/B/test runs у parent нет.

Frozen r3 manifest SHA256:
`5063bcb86289391453dee146601327c522ad6c01cc4ad86d7cebdc4081a4180a`.

## Подтверждённые результаты

| Показатель | Baseline | С пояснениями |
|---|---:|---:|
| Обязательные факты | 10/19 | 10/19 |
| Кандидаты, сумма по4запросам | 37 | 38 |
| Исходный текст, UTF8 bytes | 7204 | 7376 |
| Сохранённые полные JSON packets, bytes | 292250 | 336928 |

V-M1:0/8 в обоих вариантах; V-M2:5/6; V-M3:5/5.
Русский no-answer V-M4 пуст в обоих вариантах. При одновременно пустом
answerable русском V-M1 это не доказывает semantic no-answer способность.

Отсутствующий английский факт V-M2: «Weather decisions govern execution, not
ownership of reservations.» Найдены20из21разделов, но именно вводный раздел
с этим условием отсутствует. Description к нему также не добавило нужного
лексического совпадения. В V-M3 добавился overview.md[0:172], без новых
обязательных фактов. Доказанного прироста на двух английских вопросах тоже нет.

## Существенные границы и анализ

1. Это малая seen development проверка, не fresh holdout. Исходные разделы уже
   короткие и достаточно понятные; пояснения во многом повторяют их содержание.
   Отрицательный результат не опровергает contextual retrieval вообще.
2. Description участвует в existing low-weight routing, не в body BM25.
   Это ограниченная recipe, не полное воспроизведение Context7 или Anthropic.
   Текущий результат не разрешает менять веса/пояснения под эти вопросы.
3. В initial discovery были недооценены второй admission gate и фактическая
   граница dispatcher. Уточнение сделано до первого A/B; все промежуточные
   ошибки сохранены. limit5/budget4096 — неприменённые аргументы acquisition API,
   а не достигнутые пределы выдачи. Все returned candidates измерены без crop.
4. Description metadata видна Python-клиенту и увеличивает raw packet. Поэтому
   «retrieval-only» означает отсутствие подмены source evidence, а не невидимость
   для любого клиента. JSON bytes не равны network/provider tokens.
5. Генерация здесь — source-only harness artifact, а не встроенный автоматический
   ingestion generator. Автоматическое обновление описаний не реализовано:
   устаревший artifact отклоняется, подготовить новый должен вызывающий процесс.
6. Read-only source correctness подтверждена исходными hashes и code path;
   отдельного before/after logical SQLite witness для каждого A/B query нет.
   Не расширяем это до полного production read-only acceptance.

Вывод для дальнейшего анализа: добавление поисковых описаний не решило потерю
вводного условия даже при почти полном наборе найденных разделов. Следующий
обоснованный предмет отдельного design — выдача найденного раздела вместе с
его явно оформленным вводным контекстом. Это ранее обсуждавшийся второй шаг,
а не уже выполненное исправление или автоматическое раскрытие всех ссылок.
Нового runtime-разрешения этим review не выдаётся.
