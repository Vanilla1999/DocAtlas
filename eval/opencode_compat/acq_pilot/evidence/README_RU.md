# Свидетельства малого ACQ-пилота

Итог и ограничения: `../RESULTS_RU.md`. Вопросы и исходные цитаты:
`../oracle.json`; они не изменялись после фиксации preflight hash.

`manifest.json` перечисляет SHA256 каждого опубликованного файла, локальный
исходный путь и hash исходного артефакта. Полные артефакты остаются в
`/tmp/opencode/acq-pilot/`. Пакет около 3,9 МБ, без stores, wheel, venv и stderr.

- `L*-*.payload.json.gz`: все 14 исходных MCP text payloads, включая два
  паритета. После gzip-decompression байты идентичны исходным.
- `L*-*.metrics.json.gz`: время, raw cl100k, аргументы и source checks.
- `acquired-*.compact.json.gz`: все 36 полос фактического production
  acquisition, в исходном порядке и с неизменным текстом. Удалена часть
  metadata, JSON пересериализован: это **производные**, не сырые логи.
  Сохранены path, hashes, identity, scope, authority, line_span, section/stable
  IDs, ranking/acquisition, source_class, параметры полос и counters.
- `independent-*.json`, `review-report.json.gz`: оценка основного агента.
  Полные результаты acquisition и delivery разделены. Ранги до LIMIT —
  `independent-sql-review.json`; полный большой SQL-пул остаётся локально.
- `archive-40-lanes-vocab.json.gz`, `archive-difference-spellings.json.gz`,
  `independent-archive-explanation.json`: воспроизведение старой диагностики
  и свидетельства для восьми различий токенизации.
- `heading-comparison.json.gz`: metadata против ограниченного context_prefix.
- `corpus-manifest.json`, `quote-occurrences.json`: состав L2 и поиск точных
  альтернатив до вызовов. L0 manifest явно **postrun**, не pre-registration.
- `preflight.sha256` / `prelaunch.sha256`: записи до запусков. Пути в них
  относятся к исходной машине. Текущие опубликованные hashes — в manifest.
- `acquire-script-provenance.json`: SQL-probe после сбора был исправлен с
  scalar equality на singleton IN. Его исходная версия восстановлена, а не
  представлена как сохранённая до запуска. Это не изменило критерии/ответы.

Скрипты рядом с отчётом — исследовательские runners с явными локальными
путями, а не автономная команда установки. `prepare_corpus.py` использовал
HEAD=`4fd42299c45dc07cddb299f5f11ffbcb323e9249`; перед воспроизведением нельзя
молча заменить этот revision текущей веткой. L0 берётся из frozen `3d21bfea`
и исходного каталога; новый store создаётся изолированно. Installed-модули
проверены через `installed-module-hashes.json.gz`, а opt-in меняется только
между отдельными процессами. Процедура — `../PROTOCOL_RU.md`.

Для независимого чтения пакета достаточно `gzip -dc <file.json.gz>`.
`../review_results.py` оценивает полные локальные артефакты без новых
продуктовых вызовов; ему также нужны первичные файлы корпуса для проверки
hash/span. Пакет не является доказательством независимого holdout, полного
клиентского agent-loop или всех access/consent-сценариев.
