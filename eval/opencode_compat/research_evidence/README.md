# Публикуемый пакет свидетельств

Это сохранённые исторические данные, не новый эксперимент и не holdout. Описание
границ и ручной оценки — `../HYBRID_SIGNAL_EXPERIMENT_RU.md`; задача и готовый
промпт — `../SEARCH_RESEARCH_HANDOFF_RU.md`. Исходные вопросы и переводы:
`../original_project_questions20.json`.

- `gold20.json` — неизменённые 42 составных критерия; `gold20-source-hashes.json`
  — hashes первичных файлов; `fact-definitions.md` и `fact-matrix42.json` —
  интерпретация и ручные оценки. Возможны альтернативные допустимые источники.
- `metrics20.json` — сводка; `metrics/{off,mini,hybrid}/qNN.json` — исходные
  per-query metrics. `source-validation20.json` — исторические результаты
  off/mini; hybrid source validation записана в его per-query metrics и отчёте.
  PASS source fidelity не равен PASS фактов или проверке всех source URI.
- `responses/{off,mini,hybrid}/qNN.json.gz` — все 60 сохранённых исходных MCP
  tool texts, не полный wire transcript. Детерминированный gzip без имени и
  timestamp: `gzip -dc responses/off/q04.json.gz` возвращает исходные bytes.
  Они не редактировались; `manifest.json` фиксирует относительные имена, SHA-256
  опубликованных файлов и исходных bytes, эксперимент и исходный относительный
  путь. Сами ответы содержат repo-owned snippets и project identity hashes.
  Метрики токенов относятся к исходному несжатому тексту, не к gzip.
- Замороженный corpus восстанавливается из репозитория командой
  `git archive 3d21bfea | tar -x -C <пустой-каталог>`; сравни файлы с
  `gold20-source-hashes.json`. Этот список не является полным manifest корпуса.

Проверка на типичные секреты и абсолютные host paths проведена для включённых
артефактов; строки `API_KEY=sk-...` — опубликованные примеры-заглушки из
исходной документации, не обнаруженные credentials. Такая проверка не является
гарантией отсутствия любых секретов. Не включены stderr/traces, конфигурации,
store, модели, зависимости, приватные пути, внешний ZIP 67 MB и внешний harness.
Манифест не включает собственный hash; сами исходные данные не
реконструированы и не пересчитаны. Отдельная source-URI проверка охватывала
лишь описанные в отчёте примеры; не заявляется полный аудит всех URI.
