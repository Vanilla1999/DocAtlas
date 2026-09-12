# PR #186 — результаты вопросов

Опубликованный runtime: `3ffa12310ea699ef1c1d2044cc7a6b819eeaff12`; идентичное дерево `dd41359575f17db3eeb5d2a0b8ada5ee7c75a08d`.

Локальная версия прогона: `ea3849cee658f802076a701ae75a9b7f75973b80`.

Проверен возвращённый контекст и его цитаты. Генерация ответов живым агентом не запускалась. `needs_review` означает, что замороженный оценщик не подтвердил достаточность; это не равнозначно доказанной ошибке ответа.

Frozen-80: 31 sufficient, 25 needs_review, 24 insufficient. Среди 48 вопросов, для которых ответ должен помещаться в бюджет, достаточный контекст получен для 31. Все DTO укладываются в 800 токенов o200k_base; максимальный размер — 796.

Независимая post-hoc выборка: 5/6, без прироста относительно strict-cap.

Полные фрагменты, цитаты и оценки: [PR186_QUESTION_RESULTS.json](PR186_QUESTION_RESULTS.json).

| Набор / ID | Вопрос | Оценка | Токены | Цитаты |
|---|---|---|---:|---|
| fastapi-01 | When do FastAPI background tasks run relative to returning the response? | needs_review | 358 | docs/en/docs/tutorial/background-tasks.md:124-126 |
| fastapi-02 | Может ли task function для BackgroundTasks быть обычной def, а не async def? | needs_review | 365 | docs/en/docs/tutorial/background-tasks.md:14-22 |
| fastapi-03 | Which arguments does .add_task() receive and in what roles? | sufficient | 338 | docs/en/docs/tutorial/background-tasks.md:48-52 |
| fastapi-04 | Can allow_credentials work with allow_origins=["*"] in CORSMiddleware, and what is the default? | sufficient | 617 | docs/en/docs/tutorial/cors.md:60-61; docs/en/docs/tutorial/cors.md:53-53 |
| fastapi-05 | What identifies a CORS preflight request and which response status codes can the middleware return? | sufficient | 548 | docs/en/docs/tutorial/cors.md:67-71; docs/en/docs/tutorial/cors.md:73-75 |
| fastapi-06 | Из каких компонентов состоит origin в CORS? | needs_review | 359 | docs/en/docs/tutorial/cors.md:1-3 |
| fastapi-07 | When do FastAPI background tasks run relative to returning the response? Also identify the exact value chosen in our private production deployment. | needs_review | 358 | docs/en/docs/tutorial/background-tasks.md:124-126 |
| fastapi-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production fastapi deployment? | insufficient | 186 | — |
| fastapi-09 | Which fastapi configuration is best for our service? Our workload and deployment constraints are not specified. | insufficient | 190 | — |
| fastapi-10 | Provide every documented workflow, caveat and complete code example verbatim from all fastapi source files in this snapshot, without omissions. | insufficient | 193 | — |
| httpx-01 | What is HTTPX default timeout behavior: how long and which exception? | needs_review | 618 | docs/environment_variables.md:1-7; docs/advanced/timeouts.md:30-39 |
| httpx-02 | How can I disable all timeouts by default on an HTTPX Client? | sufficient | 618 | docs/environment_variables.md:1-7; docs/advanced/timeouts.md:30-39 |
| httpx-03 | Назови четыре типа timeout в HTTPX и объясни, что ограничивает каждый. | needs_review | 332 | docs/advanced/timeouts.md:65-71 |
| httpx-04 | What does pool timeout wait for, which exception is raised, and which argument limits connections? | sufficient | 611 | docs/advanced/timeouts.md:57-63; docs/advanced/timeouts.md:41-50 |
| httpx-05 | How can HTTPX ignore environment variables for both a Client and top-level requests? | sufficient | 618 | docs/environment_variables.md:1-7; docs/advanced/timeouts.md:6-19 |
| httpx-06 | Какие переменные задают прокси для http, https и всех запросов? | insufficient | 184 | — |
| httpx-07 | What is HTTPX default timeout behavior: how long and which exception? Also identify the exact value chosen in our private production deployment. | needs_review | 358 | docs/environment_variables.md:1-7 |
| httpx-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production httpx deployment? | insufficient | 186 | — |
| httpx-09 | Which httpx configuration is best for our service? Our workload and deployment constraints are not specified. | needs_review | 350 | docs/advanced/timeouts.md:57-63 |
| httpx-10 | Provide every documented workflow, caveat and complete code example verbatim from all httpx source files in this snapshot, without omissions. | insufficient | 193 | — |
| mkdocs-01 | Where do documentation sources and mkdocs.yml live by default? | sufficient | 372 | docs/user-guide/writing-your-docs.md:7-15 |
| mkdocs-02 | What happens when index.md and README.md are in the same directory? | sufficient | 603 | docs/user-guide/writing-your-docs.md:93-95; docs/user-guide/writing-your-docs.md:85-91 |
| mkdocs-03 | Are pages absent from nav still built, and what navigation links do they lose? | sufficient | 338 | docs/user-guide/writing-your-docs.md:163-166 |
| mkdocs-04 | Относительно чего задаются пути в nav и где лежат index.md и about.md при docs_dir=docs? | sufficient | 602 | docs/user-guide/writing-your-docs.md:109-120; docs/user-guide/writing-your-docs.md:78-83 |
| mkdocs-05 | Which page title wins when the navigation configuration and Markdown content define different titles? | needs_review | 338 | docs/user-guide/writing-your-docs.md:178-183 |
| mkdocs-06 | Can table cells contain block elements or multiple lines, and are blank lines around a table required? | needs_review | 351 | docs/user-guide/writing-your-docs.md:493-502 |
| mkdocs-07 | Where do documentation sources and mkdocs.yml live by default? Also identify the exact value chosen in our private production deployment. | needs_review | 372 | docs/user-guide/writing-your-docs.md:7-15 |
| mkdocs-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production mkdocs deployment? | insufficient | 186 | — |
| mkdocs-09 | Which mkdocs configuration is best for our service? Our workload and deployment constraints are not specified. | needs_review | 351 | docs/user-guide/writing-your-docs.md:99-103 |
| mkdocs-10 | Provide every documented workflow, caveat and complete code example verbatim from all mkdocs source files in this snapshot, without omissions. | insufficient | 197 | — |
| pydantic-01 | What can strict mode be enabled on, and what happens instead of coercing an incorrect type? | sufficient | 360 | docs/concepts/strict_mode.md:9-13 |
| pydantic-02 | Does a UUID string pass strict validation from JSON and from Python in the same way? | sufficient | 321 | docs/concepts/strict_mode.md:54-55 |
| pydantic-03 | Перечисли способы включить strict mode, включая field, annotation, config и validation call. | insufficient | 187 | — |
| pydantic-04 | What is AliasPath used to specify for validation aliases? | sufficient | 683 | docs/concepts/alias.md:16-25; docs/concepts/alias.md:27-40 |
| pydantic-05 | How does AliasGenerator help use different naming conventions when loading and saving? | needs_review | 357 | docs/concepts/alias.md:129-137 |
| pydantic-06 | В чём различие alias_priority=1 и alias_priority=2? | sufficient | 381 | docs/concepts/alias.md:192-200 |
| pydantic-07 | What can strict mode be enabled on, and what happens instead of coercing an incorrect type? Also identify the exact value chosen in our private production deployment. | needs_review | 338 | docs/concepts/strict_mode.md:48-52 |
| pydantic-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production pydantic deployment? | insufficient | 187 | — |
| pydantic-09 | Which pydantic configuration is best for our service? Our workload and deployment constraints are not specified. | insufficient | 191 | — |
| pydantic-10 | Provide every documented workflow, caveat and complete code example verbatim from all pydantic source files in this snapshot, without omissions. | insufficient | 194 | — |
| ruff-01 | Does enabling preview automatically enable all preview rules? | needs_review | 796 | docs/preview.md:33-58; docs/preview.md:10-15; docs/configuration.md:599-602 |
| ruff-02 | Как включить Ruff preview через CLI или configuration file? | sufficient | 625 | docs/preview.md:10-31; docs/configuration.md:457-464 |
| ruff-03 | Since which version can preview be configured separately for linting and formatting? | sufficient | 399 | docs/preview.md:10-31 |
| ruff-04 | What happens if a deprecated rule is explicitly selected while preview is enabled? | sufficient | 603 | docs/preview.md:184-187; docs/preview.md:60-79 |
| ruff-05 | What happens to explicit-preview-rules when preview mode is disabled? | sufficient | 624 | docs/preview.md:157-171; docs/preview.md:173-182 |
| ruff-06 | Does Ruff merge parent configuration files, and what explicit mechanism supports inheritance? | sufficient | 365 | docs/configuration.md:278-284 |
| ruff-07 | Does enabling preview automatically enable all preview rules? Also identify the exact value chosen in our private production deployment. | insufficient | 192 | — |
| ruff-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production ruff deployment? | insufficient | 186 | — |
| ruff-09 | Which ruff configuration is best for our service? Our workload and deployment constraints are not specified. | insufficient | 190 | — |
| ruff-10 | Provide every documented workflow, caveat and complete code example verbatim from all ruff source files in this snapshot, without omissions. | needs_review | 332 | docs/configuration.md:466-469 |
| starlette-01 | If one BackgroundTasks function raises an exception, what happens to later tasks and their ordering? | needs_review | 293 | docs/background.md:42-46 |
| starlette-02 | Will Starlette serve incoming requests before its lifespan handler has run? | sufficient | 603 | docs/lifespan.md:27-33; docs/lifespan.md:2-25 |
| starlette-03 | Когда начинается lifespan teardown относительно connections и background tasks? | sufficient | 333 | docs/lifespan.md:27-33 |
| starlette-04 | Is request state a deep or shallow copy of lifespan state? | sufficient | 470 | docs/lifespan.md:73-74; docs/lifespan.md:35-38 |
| starlette-05 | How should I use TestClient to ensure lifespan runs in tests? | sufficient | 458 | docs/lifespan.md:76-92 |
| starlette-06 | Какая сигнатура BackgroundTask добавляет одну фоновую задачу к response? | sufficient | 291 | docs/background.md:7-11 |
| starlette-07 | If one BackgroundTasks function raises an exception, what happens to later tasks and their ordering? Also identify the exact value chosen in our private production deployment. | needs_review | 293 | docs/background.md:42-46 |
| starlette-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production starlette deployment? | insufficient | 186 | — |
| starlette-09 | Which starlette configuration is best for our service? Our workload and deployment constraints are not specified. | insufficient | 190 | — |
| starlette-10 | Provide every documented workflow, caveat and complete code example verbatim from all starlette source files in this snapshot, without omissions. | insufficient | 193 | — |
| typer-01 | Does raising typer.Exit() itself imply an error, and what is its default exit code? | sufficient | 641 | docs/tutorial/terminating.md:55-67; docs/tutorial/terminating.md:7-17 |
| typer-02 | Как через typer.Exit сообщить терминалу об ошибке? | sufficient | 450 | docs/tutorial/terminating.md:55-67 |
| typer-03 | What visible message distinguishes aborting a Typer program from a normal Exit? | needs_review | 382 | docs/tutorial/parameter-types/bool.md:107-134 |
| typer-04 | How do I give a boolean option alternative positive and negative names such as --accept and --reject? | sufficient | 414 | docs/tutorial/parameter-types/bool.md:71-87 |
| typer-05 | Как записать только отрицательное имя boolean option: важен ли пробел перед /? | insufficient | 185 | — |
| typer-06 | What happens to --no-force when I declare only the --force option? | sufficient | 714 | docs/tutorial/parameter-types/bool.md:39-67; docs/tutorial/parameter-types/bool.md:7-27 |
| typer-07 | Does raising typer.Exit() itself imply an error, and what is its default exit code? Also identify the exact value chosen in our private production deployment. | needs_review | 378 | docs/tutorial/terminating.md:55-67 |
| typer-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production typer deployment? | insufficient | 185 | — |
| typer-09 | Which typer configuration is best for our service? Our workload and deployment constraints are not specified. | insufficient | 189 | — |
| typer-10 | Provide every documented workflow, caveat and complete code example verbatim from all typer source files in this snapshot, without omissions. | insufficient | 192 | — |
| uv-01 | Does uv read pip.conf or PIP_INDEX_URL? | sufficient | 322 | docs/pip/compatibility.md:17-20 |
| uv-02 | В каких двух случаях uv принимает pre-release версии по умолчанию? | sufficient | 352 | docs/pip/compatibility.md:41-47 |
| uv-03 | What can I do when dependency resolution fails due to a transitive pre-release? | sufficient | 667 | docs/pip/compatibility.md:49-53; docs/pip/compatibility.md:41-47 |
| uv-04 | How does uv restrict candidate versions across multiple indexes and why? | needs_review | 794 | docs/pip/compatibility.md:140-142; docs/pip/compatibility.md:122-126; docs/pip/compatibility.md:117-120 |
| uv-05 | Compare first-match, unsafe-first-match and unsafe-best-match index strategies. | needs_review | 356 | docs/pip/compatibility.md:143-146 |
| uv-06 | Which build isolation mode does uv use by default and what is the escape hatch for a missing build dependency? | needs_review | 379 | docs/pip/compatibility.md:162-168 |
| uv-07 | Does uv read pip.conf or PIP_INDEX_URL? Also identify the exact value chosen in our private production deployment. | needs_review | 322 | docs/pip/compatibility.md:17-20 |
| uv-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production uv deployment? | insufficient | 189 | — |
| uv-09 | Which uv configuration is best for our service? Our workload and deployment constraints are not specified. | needs_review | 328 | docs/pip/compatibility.md:190-192 |
| uv-10 | Provide every documented workflow, caveat and complete code example verbatim from all uv source files in this snapshot, without omissions. | insufficient | 196 | — |
| httpcore-01 | Does HTTP Core handle redirects and session cookie handling for the caller? | sufficient | 323 | README.md:11-15 |
| httpcore-02 | Which async backends does HTTP Core support? | sufficient | 333 | README.md:17-24 |
| itsdangerous-01 | How does ItsDangerous ensure that a token has not been tampered with? | sufficient | 340 | README.md:3-13 |
| itsdangerous-02 | Can ItsDangerous add a timestamp and verify it automatically when loading a token? | sufficient | 340 | README.md:3-13 |
| sqlmodel-01 | What does SQLModel use for everything in this tutorial, and what editor support does that enable? | needs_review | 565 | docs/tutorial/index.md:1-3; docs/tutorial/index.md:5-11 |
| sqlmodel-02 | Are the tutorial code blocks intended to be copied and used directly? | sufficient | 363 | docs/tutorial/index.md:23-29 |
