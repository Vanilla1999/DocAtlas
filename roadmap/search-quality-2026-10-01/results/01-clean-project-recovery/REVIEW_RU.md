# Ревью clean-Git recovery перед коммитом

**Вывод:** блокирующих замечаний к узкой clean-Git правке не обнаружено. Это самостоятельное ревью того же агента, не независимый reviewer gate.

## Найдено и исправлено

**Повторяемость before-runner:** сравнение baseline wheel с текущим HEAD перестало бы работать после коммита исправления. Runner теперь использует pinned `--baseline-commit`, по умолчанию `5cd7515c`; provenance сохраняет точный reference commit. Ранее сохранённые wires не переписывались.

## Проверено

- Источник clean permission — серверный Git/preflight, не вопрос или содержимое README. Пустой индекс не превращается в semantic support/edit authorization.
- Digest передаётся без пересоздания; mutation повторно проверяет HEAD, worktree и preflight. `auto_execute=false` сохраняется.
- Новая operational ветка ограничена project lane без evidence/confirmation; no-Git, dirty/indeterminate, invalid catalog, module-not-found, stale/ready не получают её ошибочно.
- Public serialization и installed-wheel stdio; архивные evidence bytes не изменены. Production diff — только три исходных файла, без retrieval/scorer/budget/default/dependency изменений.
- Pytest logs сохранены verbatim; локальный whitespace attribute касается только `*.log` в этой папке, не production/test source.
- Повторно прошли [29 regression cases](review-regression.log) и [131 соседний contract/recovery test](review-related.log); [installed-wheel stdio smoke](review-after/result.json) также PASS.

## Известные ограничения, не скрытые ревью

Legacy no-Git confirmation policy не исправлена: исходный шаг 01 закрыт только в clean-Git части. Три поисковых failures расширенного прогона подтверждены на baseline и остаются открытыми. Полный suite и независимая end-to-end панель не объявляются пройденными; шаг 02 не начинался.
