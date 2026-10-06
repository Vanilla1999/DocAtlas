# Архив завершённых веток #211 — 2026-10-06

Удаление временных веток разрешено владельцем. Основная интеграционная ветка
`integration/stage3-v2-identity-pr1` сохранена на
`37bfd0668f819935dd9e027bd9d8bf767fcd185a`.

## Отчёты для чтения

- [A: strict attribute](parallel-strict-attribute-REPORT_RU.md)
- [B: authority](parallel-authority-REPORT_RU.md)
- [C: hint](parallel-hint-REPORT_RU.md)
- [Независимое review](parallel-review-REPORT_RU.md)
- [Упрощение маршрутов](simplify-routes-REPORT_RU.md)
- [Семантика решений](simplify-decisions-REPORT_RU.md)
- [Нативные controls](simplify-controls-REPORT_RU.md)

Это сохранённые исходные отчёты. Пути к прежним worktrees в них теперь исторические;
окончательный вердикт A — BLOCKED, B — не принят. Архивирование не означает принятия
patch, тестовых ожиданий или готовности merge.

## Состав и целостность

Семь `.tar.gz` содержат 140 изменённых/новых файлов агентов, включая отчёты,
кандидатные tests/manifests, scripts, captures, логи и JUnit. В каждом архиве:

- `files/` — точные bytes новых и изменённых файлов;
- `tracked.patch` — полный tracked diff относительно HEAD, включая binary changes;
- `index.patch` — staged diff отдельно;
- `status.txt` — исходный git status;
- `metadata.json` — ветка, HEAD, перечень файлов, размеры и hashes.

[MANIFEST.json](MANIFEST.json) хранит SHA-256 архивов и файлов. Каждый архив прочитан
обратно и сравнен с live bytes перед удалением worktree; перед удалением повторно
проверены hashes, SHA ветки и status. Неизменённые tracked files не дублировались:
их baseline указан в metadata. `__pycache__` и `.pytest_cache` исключены; иных ignored
файлов в проверенных worktrees не найдено.

[CLEANUP.json](CLEANUP.json) — точный список удалённых refs/worktree registrations
и сохранённых исторических SHA. Удалено 13 локальных веток, 7 живых временных
worktrees и 5 записей уже отсутствовавших stage3 worktrees. Устаревшая локальная
`origin/pr211-merge` удалена после проверки отсутствия соответствующего head на
сервере; её SHA сохранён tag `archive/pr211-cleanup-20261006/stale-pr211-merge`.
Удалений remote branches не было: нужные старые remote branches уже отсутствовали.

## Как вернуться к результатам

1. Выбрать архив и взять baseline SHA из metadata.
2. Создать отдельный worktree от этого SHA.
3. Применить `tracked.patch` к baseline и восстановить новые файлы из `files/`.
   В `files/` также лежат полные конечные версии изменённых tracked files.
4. Проверить восстановленные bytes по hashes из manifest.
5. Использовать команды выбранного отчёта, заменив исторический worktree path на
   новый. Candidate A и reviewer snapshot содержат заблокированный patch, не baseline.

Архив хранится вместе с документацией #211 в `v2plan`. Владелец отдельно разрешил
commit/push документов и архивов. Их публикация не меняет вердикты кандидатов
и не является переносом содержащихся в архивах patches в продуктовый код.
