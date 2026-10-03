# Восемь вопросов для этапа 04

Статус: зафиксированы до агентских запусков; ответы ещё не получены.
Это exposed/development вопросы, не unseen validation.
Ожидания ниже предназначены только оценщику, не агенту.
Sources — unchanged snapshot из `eval/evidence_quality_v2/sources/`;
version/ref задаётся `source-manifest.json`. Агенту выдавать соответствующий
project corpus и вопрос, без expectations и готовых lookup.

## Полный ответ

1. `When do FastAPI background tasks run relative to returning the response?`
   Ожидание: after returning the response.
   Source: `fastapi/docs/en/docs/tutorial/background-tasks.md:3`.
2. `How can I disable all timeouts by default on an HTTPX Client?`
   Ожидание: `httpx.Client(timeout=None)`.
   Source: `httpx/docs/advanced/timeouts.md:38`.

## Составной ответ

3. `If one Starlette BackgroundTasks function raises an exception, what happens to later tasks and their ordering?`
   Ожидание: execution in order; following tasks do not run after an exception.
   Source: `starlette/docs/background.md:77-78`.
4. `What does HTTPX pool timeout wait for, which exception is raised, and which argument limits connections?`
   Ожидание: acquiring a connection from pool; `PoolTimeout`; `limits`.
   Source: `httpx/docs/advanced/timeouts.md:57-61`.

## Частичный / отсутствующий ответ

5. `What is HTTPX default timeout behavior: how long and which exception? Also identify the exact value chosen in our private production deployment.`
   Ожидание: `TimeoutException` after 5 seconds of network inactivity;
   private production value unknown, не выдавать default за deployment value.
   Source: `httpx/docs/advanced/timeouts.md:3-4`.
   Private configuration не присутствует в выбранном corpus.
6. `What is the guaranteed 99th-percentile latency in milliseconds for our production FastAPI deployment?`
   Ожидание: unknown; запросить измерения/данные deployment, не выдумывать число.
   В выбранном FastAPI corpus гарантия конкретного deployment не задана.

## Чужой subject / другое условие

7. `Does the Ruff documentation about explicitly selecting deprecated rules with preview enabled establish an error when preview is disabled?`
   Ожидание: правило про enabled нельзя переносить на disabled; поведение
   disabled не подтверждено этим правилом. Не заявлять «ошибки точно нет».
   Source: `ruff/docs/preview.md:186-187`, правило условно: preview enabled.
8. `Does uv ignoring pip.conf and PIP_INDEX_URL establish that pip itself ignores them?`
   Ожидание: не переносить поведение uv на pip. Source утверждает только uv
   behavior; поведение pip не доказывается этим утверждением.
   Source: `uv/docs/pip/compatibility.md:19-20`.

Для всех вопросов: claims поддержаны фактически доставленными snippets,
citations соответствуют claims, нет unsupported additions и бесполезных retries.
Проверять остальные доступные snippets тоже: ожидания unknown не разрешают
игнорировать другое явное доказательство в final packet.
