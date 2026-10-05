# Продолжение этапа 3: BLOCKED_EVIDENCE_IDENTITY_AND_CI

Дата: 2026-10-05. Это отчёт о диагностике, не исправление продукта и не разрешение merge.

## Зафиксированные ветки

- main: d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c.
- PR-1 #206, fix/next07-pr1-output-integrity: 596eeb36b66a474b2b5d246fd6bd834b6dcbb5c6; draft, не слит.
- Создан контроль #207, diagnostic/main-gates-d2ed5c4c: bf89ee4a15c76bbbd96a3c65015d01d80d5a92e5.
- Полный diff main→контроль: один коммит, один файл v2plan/main-gates/PROTOCOL_RU.md, 31 добавленная строка. Runtime, tests, labels и workflows в контрольной ветке не изменены.
- Research перед этим отчётом: 0e9c72a8e701f6ef40298ef6f7155765c8e76171.

## Что выполнено

1. Проверено актуальное состояние PR-1 и исходной базы. Main и PR-1 этой работой не изменены.
2. Прочитаны исходники service/scope, доступные тесты, workflow и прежние failed logs. Причины selector validation, scope delivery и answer applicability не объединялись в одно исправление.
3. Создан отдельный documentation-only контроль с заранее заданными verdict и STOP. Открыт draft PR #207, чтобы исполнить существующие workflows без их модификации.
4. Получены контрольные run IDs: CI 37303582475, release 37303582461, P1.6 37303582442. Прочитаны результаты и логи; загружен доступный artifact.
5. Запрошен повтор только failed jobs PR-1: run 37298795100, attempt 2. Новый код PR-1 не создавался. Допуск CI не получен.

## Почему исправление scope/answer сейчас НЕ заявлено

Не удалось надёжно связать прежний список пяти failures с исходниками и сопоставимым новым выполнением.

В частности, файлы tests/docs/test_compositional_task_matrix.py и tests/docs/test_unified_context_service_pipeline_surface.py из прежнего списка failures не были получены по закреплённым refs. Повторный запрос первого файла непосредственно по exact main SHA также вернул Contents API 404. Это наблюдение об операции чтения, не доказательство отсутствия файла во всех возможных checkout и не доказательство причины сбоя CI.

Контрольные результаты, прочитанные job logs и загруженный artifact не удалось свести в один подтверждённый набор test source → fixture → callable → request → assertion на одной revision. Среди полученных материалов есть разные наборы команд и результатов. Поэтому числа из отдельных ответов инструментов не складываются в общий PASS и не используются для утверждения, что прежние пять failures исчезли или исправлены.

При заключительном локальном чтении ZIP next07-main-control-37303582475.zip он содержал project-context-quality-hermetic.json и project-context-quality-legacy-live.json. Первый обозначает alias_and_query_plan_contract с retrieval_executed=false; второй — live_self_host. Они не являются автоматически воспроизведением пяти pytest assertions прежнего отчёта. Их принятие за такое воспроизведение было бы ошибкой.

Источник расхождения не установлен. Не заявляется ни повреждение репозитория, ни вина GitHub, ни продуктовая регрессия по одному только несоответствию полученных материалов.

Важная поправка к предыдущему отчёту: сравнение старых CI logs было историческим наблюдением. Оно НЕ закрывает причинную привязку текущего failure к конкретной функции и не является готовым заданием «исправить эти пять мест».

## Сохранённые границы

Новых runtime-исправлений в этой итерации нет. Тесты, frozen expectations, labels, gates, parser, ranking, admission, source/security/identity/scope/version/snapshot guards и MCP API не менялись. Новые workflows не добавлялись. Никаких skip/xfail, обходов CI или force-push.

PR #207 — диагностический контроль, не второй продуктовый PR и не замена PR-2. Его не следует сливать как исправление.

Main merge: NOT_DONE. PR-1: draft. Отдельное одобрение и полный допуск CI остаются обязательными. N10, PR-2, 80/49/54 retention и модельные эксперименты этой работой не запускались.

## Конечный следующий допуск — один связанный evidence bundle

До следующей продуктовой правки нужен результат из одного проверяемого checkout:

1. git HEAD, его parents, git status, полный tracked-file manifest и SHA-256 workflow, вызываемой команды, test module, fixture и импортированного runtime module.
2. Фактическая pytest collection либо явный отчёт, что данный node ID в этой revision отсутствует. Не подставлять одноимённый тест другой версии.
3. Исходный request, raw response, traceback/assertion и exit code, полученные тем же процессом. Отдельно сохранить dependency versions и точный файл, из которого импортирована функция.
4. Проверить, что после выполнения исходники и ожидания неизменны. Сохранить сырые файлы, а не только пересказ результата.

DONE этого допуска: каждый разбираемый failure связан с доступным исходником и фактическим вызовом одной revision. Только затем отдельный patch на одну доказанную ответственность, review и исходные positives/negatives.

REJECTED продуктового patch: обязательный контроль нарушен; правила не расширять в текущем замере.

BLOCKED: связать execution с исходниками не удалось. Не делать speculative guard fix и не считать старый failure разрешением пропустить gate.

Этапы 1–2 PR-1 остаются выполненными в ранее заявленной области. Этап 3 не закрыт. Это конечный отчёт текущей диагностической попытки; автоматическое продолжение, merge и rollout не назначены.

## Ссылки

- https://github.com/Vanilla1999/DocAtlas/pull/206
- https://github.com/Vanilla1999/DocAtlas/pull/207
- https://github.com/Vanilla1999/DocAtlas/actions/runs/37303582475
- https://github.com/Vanilla1999/DocAtlas/actions/runs/37303582442
- https://github.com/Vanilla1999/DocAtlas/actions/runs/37303582461
- https://github.com/Vanilla1999/DocAtlas/actions/runs/37298795100
