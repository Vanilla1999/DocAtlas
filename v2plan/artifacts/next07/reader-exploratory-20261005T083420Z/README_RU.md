# Exploratory transport bridge — НЕ published live pilot

Разрешённая пользователем exploratory revision: ordinary general subagents
openai/gpt-6.1-sol, с признанным coding-context contamination, без API ключа.
Этот runner не вызывает модель и не создаёт агентов. Python существующей .venv
3.13.12 разрешён как явное отклонение от published 3.12. Dependencies не меняются.
Не запускались N10, полный suite, published native scripted reads или live pilot.

## Scope и авторская transport-проверка до запуска

Изменения только в этом новом каталоге; production/tests/protocol не изменяются.
load_cases → isolated_service/index_project → capture_arm(C, COMPACT_READ_LIMITS)
→ audit_payload. Один настоящий initial C packet на case, одинаковый для A/B.
Services живут в ExitStack до завершения HTTP bridge. Каждый arm имеет собственный
SectionHost, random handles и независимые attempts/evidence. Hosts создаются при
первом GET input; повторный GET не создаёт host, не продлевает срок и не делает read.
Gateway native authorize/read_snapshot/authorize, caps и prompts не меняются.
Никаких pre-reads и передачи целевого section модели. Frozen hashes проверяются
перед reader inputs/actions. Авторская проверка не является independent review.

## Operator API (только localhost)

Порт/PID: bridge-ready.json. Соответствие case/arm/opaque session URLs:
operator-session-map-private.json. Это файл ТОЛЬКО организатора, НЕ reader.
Статус 10 packets: initial-status.json; capture/audit: native/*/initial/capture.json.

`GET /input/<session>` возвращает только `system`, `question`, `first_view`, `tools`.
SYSTEM/schema без изменений: system-and-schemas.json. Передавать reader только
этот JSON, не README, metadata, private map, пути evidence, rubric или gold.
Ни case IDs, ни arm label нет в этом JSON. Native opaque project paths и public
evidence IDs сохраняются как есть; не вычищать первый packet. Arm A не получает
navigation/read schema. B получает только selected-documents navigation.

Создавать отдельную reader-сессию на arm. Если general subagent имеет доступ к
repo/shell/web или наследуемой памяти, это contamination, а не strict isolation;
инструктировать его не использовать такие возможности, не объявлять validated.
Организатор не выбирает handle за reader и не отвечает вместо reader.

`POST /read/<session>` с JSON `{"handle":"<выбранный reader handle>"}` выполняет
настоящий SectionHost.read_section. Вернуть reader ТОЛЬКО actual JSON response.
Не более двух attempts B, включая unavailable. A запрещён. Между inputs и
read действует исходный TTL 600 секунд; не продлевать/сбрасывать/пересоздавать host.
После двух attempts следующий advertised инструмент — только submit_answer:
оператор обязан убрать read schema из tools; SYSTEM/finish schema остаются прежними.
Сохранять raw reader requests/results у организатора для последующего review.

`POST /finish/<session>`:

```json
{
  "finish": {
    "status": "unknown",
    "answer": "",
    "citations": [],
    "missing": "...",
    "question_for_user": ""
  },
  "reader_result": "verbatim raw reader output/transcript, or a JSON object",
  "reader_metadata": {"model": "openai/gpt-6.1-sol", "host": "general-subagent", "session_id": "...", "coding_context_contamination": true}
}
```

Значения finish принадлежат reader, пример НЕ является ответом/заготовкой.
Без исправления/подсказки сохранять malformed/refusal/incomplete в reader_result;
не invent valid finish. Malformed envelope/schema закрывает arm как INVALID,
сохраняет raw POST, не делает repair/retry. Корректный finish сохраняет exact-quote
contract errors отдельно от semantic review. Повторный finish не перезаписывает.
Результат/evidence: sessions/<session>/result.json, transport-events.json и raw POST.

Запросы:

```bash
curl --fail-with-body "http://127.0.0.1:<port>/input/<session>"
curl --fail-with-body -H 'Content-Type: application/json' --data-binary @read.json "http://127.0.0.1:<port>/read/<session>"
curl --fail-with-body -H 'Content-Type: application/json' --data-binary @finish.json "http://127.0.0.1:<port>/finish/<session>"
```

Не передавать reader эти URLs как доступ к private evidence/repo. Это transport
оператора, НЕ новые MCP tools. Localhost не защищает от других локальных процессов;
каталог chmod 700, opaque routes, никакого внешнего bind. Не публиковать dirty.patch
и installed metadata без secret review. Credentials/environment не выводятся.

## Запуск и evidence

Команда: `DOCATLAS_OFFLINE=1 .venv/bin/python <этот каталог>/bridge.py`.
Лог bridge.log; interpreter/dependencies, HEAD/branch, dirty.patch, status,
untracked hashes, preflight hashes и metadata command exit codes сохраняются.
initial-capture-exit.json отражает 10 native calls; bridge-exit.json появится только
после остановки. Для штатной остановки оператором: `kill -TERM <pid>`.
Остановка пишет postflight hashes. Background process всё время HTTP sessions жив.

Статусы bridge/packets — только техническая готовность exploratory transport,
НЕ READY_NATIVE published, НЕ VALIDATED_LOCAL_PILOT, НЕ semantic acceptance/rollout.
Внешние reader/reviewer orchestration, 20 сессий и качество не исполнены runner.
