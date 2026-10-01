# Search audit — 2026-10-01

Основной результат: [ANALYSIS_RU.md](ANALYSIS_RU.md).

- [Каждый из 80 вопросов по проекту](PROJECT_80_REVIEW_RU.md)
- [Каждый из frozen 80 по библиотекам](EXTERNAL_80_REVIEW_RU.md)
- [Grounded и Context7](COMPARATORS_RU.md)
- [Конечный план исправлений и acceptance](ACTION_PLAN_RU.md)

`raw/` сохраняет официальные ответы, запросы и отдельные derived оценки.
`corpus/` содержит 148 byte-preserved исходных документов (134 project + 14 external).
`backup/` — исходный локальный SQLite и configs до очистки.
`artifact-manifest.json` содержит SHA256 всех сохранённых файлов, кроме самого manifest
и generated Python caches. `raw/artifact-verification.json` — полнота и method checks.

Проверены 320 основных installed-DocAtlas stdio запросов, 180 Grounded searches,
10 Context7 questions, 10 дополнительных question-only translations и 76
instrumented handler calls. Это diagnostics, не новый independent product gate.

Production runtime, defaults, thresholds и зависимости проекта не менялись.
После rebuild текущий проект имеет `project_docs_ready`, 134/134 indexed,
stale=0. Shared Qdrant и чужие проекты не очищались.

## Повторение

Python scripts в этой папке фиксируют локальные пути и протокол исполнения.
Использовался `/home/viadmin/.local/share/uv/tools/doc-atlas/bin/python`;
production imports берутся из установленного пакета, eval observers — из checkout.
Grounded Node entry: `/tmp/opencode/search-audit-tools-20261001/node_modules/@arabold/docs-mcp-server/dist/index.js`.

Не запускать все scripts поверх этой папки: они могут перезаписать собственные
generated outputs, а lifecycle probes предназначены для одноразовых fixtures.
Для нового прогона скопировать runners в новую audit папку, выделить новые
WORK/DOCATLAS_HOME/store paths и заново проверить corpus/runtime pins.
`verify_artifacts.py` и `reassess_public_integrity.py` не вызывают product tools.

Авторские ручные verdicts сохранены в `manual_*_review.json`; они не скрыты
за агрегированным процентом и не заменяют независимого reviewer.
