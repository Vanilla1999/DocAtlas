# Все frozen 80: свежие MCP-результаты

Внешние pinned Markdown snapshots импортированы как **local project docs**, не через dependency/library prefetch. Это диагностика retrieval/packing, не проверка resolver/lockfile/network pipeline. 48 within_budget positives и 32 partial/unanswerable/ambiguous/over_budget controls. Слово `needs_review` не означает автоматический провал.

| ID | Вопрос | Answerability | DocAtlas frozen scorer | DocAtlas semantic review | Grounded scorer / formatting check | DA / G3 tokens |
|---|---|---|---|---|---|---|
| fastapi-01 | When do FastAPI background tasks run relative to returning the response? | within_budget | sufficient | full | sufficient / True | 765 / 852 |
| fastapi-02 | Может ли task function для BackgroundTasks быть обычной def, а не async def? | within_budget | sufficient | full | sufficient / True | 797 / 713 |
| fastapi-03 | Which arguments does .add_task() receive and in what roles? | within_budget | sufficient | full | needs_review / True | 755 / 915 |
| fastapi-04 | Can allow_credentials work with allow_origins=["*"] in CORSMiddleware, and what is the default? | within_budget | sufficient | full | needs_review / False | 790 / 1234 |
| fastapi-05 | What identifies a CORS preflight request and which response status codes can the middleware return? | within_budget | sufficient | full | needs_review / True | 786 / 1030 |
| fastapi-06 | Из каких компонентов состоит origin в CORS? | within_budget | sufficient | full | sufficient / True | 789 / 1205 |
| fastapi-07 | When do FastAPI background tasks run relative to returning the response? Also identify the exact value chosen in our private production deployment. | partial | needs_review | control | needs_review / not_positive | 765 / 852 |
| fastapi-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production fastapi deployment? | unanswerable | insufficient | control | needs_review / not_positive | 207 / 701 |
| fastapi-09 | Which fastapi configuration is best for our service? Our workload and deployment constraints are not specified. | ambiguous | insufficient | control | needs_review / not_positive | 211 / 722 |
| fastapi-10 | Provide every documented workflow, caveat and complete code example verbatim from all fastapi source files in this snapshot, without omissions. | over_budget | insufficient | control | needs_review / not_positive | 214 / 518 |
| httpx-01 | What is HTTPX default timeout behavior: how long and which exception? | within_budget | sufficient | full | sufficient / True | 740 / 1181 |
| httpx-02 | How can I disable all timeouts by default on an HTTPX Client? | within_budget | sufficient | full | sufficient / True | 790 / 1181 |
| httpx-03 | Назови четыре типа timeout в HTTPX и объясни, что ограничивает каждый. | within_budget | sufficient | full | needs_review / False | 800 / 1181 |
| httpx-04 | What does pool timeout wait for, which exception is raised, and which argument limits connections? | within_budget | sufficient | full | needs_review / True | 776 / 1181 |
| httpx-05 | How can HTTPX ignore environment variables for both a Client and top-level requests? | within_budget | sufficient | full | needs_review / True | 780 / 1231 |
| httpx-06 | Какие переменные задают прокси для http, https и всех запросов? | within_budget | sufficient | full | sufficient / True | 661 / 1231 |
| httpx-07 | What is HTTPX default timeout behavior: how long and which exception? Also identify the exact value chosen in our private production deployment. | partial | needs_review | control | needs_review / not_positive | 793 / 1181 |
| httpx-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production httpx deployment? | unanswerable | insufficient | control | needs_review / not_positive | 207 / 1231 |
| httpx-09 | Which httpx configuration is best for our service? Our workload and deployment constraints are not specified. | ambiguous | needs_review | control | needs_review / not_positive | 741 / 1503 |
| httpx-10 | Provide every documented workflow, caveat and complete code example verbatim from all httpx source files in this snapshot, without omissions. | over_budget | insufficient | control | needs_review / not_positive | 214 / 1503 |
| mkdocs-01 | Where do documentation sources and mkdocs.yml live by default? | within_budget | sufficient | full | sufficient / True | 794 / 2093 |
| mkdocs-02 | What happens when index.md and README.md are in the same directory? | within_budget | sufficient | full | sufficient / True | 751 / 2093 |
| mkdocs-03 | Are pages absent from nav still built, and what navigation links do they lose? | within_budget | sufficient | full | sufficient / True | 799 / 2093 |
| mkdocs-04 | Относительно чего задаются пути в nav и где лежат index.md и about.md при docs_dir=docs? | within_budget | sufficient | full | sufficient / True | 793 / 2093 |
| mkdocs-05 | Which page title wins when the navigation configuration and Markdown content define different titles? | within_budget | sufficient | full | sufficient / True | 779 / 3087 |
| mkdocs-06 | Can table cells contain block elements or multiple lines, and are blank lines around a table required? | within_budget | needs_review | full | needs_review / False | 782 / 2985 |
| mkdocs-07 | Where do documentation sources and mkdocs.yml live by default? Also identify the exact value chosen in our private production deployment. | partial | needs_review | control | needs_review / not_positive | 797 / 2093 |
| mkdocs-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production mkdocs deployment? | unanswerable | insufficient | control | needs_review / not_positive | 207 / 2136 |
| mkdocs-09 | Which mkdocs configuration is best for our service? Our workload and deployment constraints are not specified. | ambiguous | needs_review | control | needs_review / not_positive | 783 / 2953 |
| mkdocs-10 | Provide every documented workflow, caveat and complete code example verbatim from all mkdocs source files in this snapshot, without omissions. | over_budget | needs_review | control | needs_review / not_positive | 792 / 3177 |
| pydantic-01 | What can strict mode be enabled on, and what happens instead of coercing an incorrect type? | within_budget | sufficient | full | sufficient / True | 757 / 1493 |
| pydantic-02 | Does a UUID string pass strict validation from JSON and from Python in the same way? | within_budget | sufficient | full | sufficient / True | 794 / 1558 |
| pydantic-03 | Перечисли способы включить strict mode, включая field, annotation, config и validation call. | within_budget | sufficient | full | sufficient / True | 791 / 1652 |
| pydantic-04 | What is AliasPath used to specify for validation aliases? | within_budget | sufficient | full | sufficient / True | 695 / 1905 |
| pydantic-05 | How does AliasGenerator help use different naming conventions when loading and saving? | within_budget | sufficient | full | needs_review / True | 786 / 2133 |
| pydantic-06 | В чём различие alias_priority=1 и alias_priority=2? | within_budget | sufficient | full | needs_review / False | 467 / 350 |
| pydantic-07 | What can strict mode be enabled on, and what happens instead of coercing an incorrect type? Also identify the exact value chosen in our private production deployment. | partial | needs_review | control | needs_review / not_positive | 762 / 1493 |
| pydantic-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production pydantic deployment? | unanswerable | insufficient | control | needs_review / not_positive | 208 / 1857 |
| pydantic-09 | Which pydantic configuration is best for our service? Our workload and deployment constraints are not specified. | ambiguous | insufficient | control | needs_review / not_positive | 212 / 1905 |
| pydantic-10 | Provide every documented workflow, caveat and complete code example verbatim from all pydantic source files in this snapshot, without omissions. | over_budget | insufficient | control | needs_review / not_positive | 215 / 1671 |
| ruff-01 | Does enabling preview automatically enable all preview rules? | within_budget | sufficient | full | sufficient / True | 758 / 2989 |
| ruff-02 | Как включить Ruff preview через CLI или configuration file? | within_budget | sufficient | full | sufficient / True | 784 / 1091 |
| ruff-03 | Since which version can preview be configured separately for linting and formatting? | within_budget | sufficient | full | sufficient / True | 775 / 4948 |
| ruff-04 | What happens if a deprecated rule is explicitly selected while preview is enabled? | within_budget | sufficient | full | sufficient / True | 745 / 943 |
| ruff-05 | What happens to explicit-preview-rules when preview mode is disabled? | within_budget | sufficient | full | sufficient / True | 781 / 1168 |
| ruff-06 | Does Ruff merge parent configuration files, and what explicit mechanism supports inheritance? | within_budget | sufficient | full | sufficient / True | 737 / 2398 |
| ruff-07 | Does enabling preview automatically enable all preview rules? Also identify the exact value chosen in our private production deployment. | partial | needs_review | control | needs_review / not_positive | 728 / 2989 |
| ruff-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production ruff deployment? | unanswerable | insufficient | control | needs_review / not_positive | 207 / 2536 |
| ruff-09 | Which ruff configuration is best for our service? Our workload and deployment constraints are not specified. | ambiguous | needs_review | control | needs_review / not_positive | 777 / 3507 |
| ruff-10 | Provide every documented workflow, caveat and complete code example verbatim from all ruff source files in this snapshot, without omissions. | over_budget | needs_review | control | needs_review / not_positive | 798 / 5398 |
| starlette-01 | If one BackgroundTasks function raises an exception, what happens to later tasks and their ordering? | within_budget | sufficient | full | sufficient / True | 553 / 1308 |
| starlette-02 | Will Starlette serve incoming requests before its lifespan handler has run? | within_budget | sufficient | full | sufficient / True | 699 / 999 |
| starlette-03 | Когда начинается lifespan teardown относительно connections и background tasks? | within_budget | sufficient | full | sufficient / True | 760 / 1003 |
| starlette-04 | Is request state a deep or shallow copy of lifespan state? | within_budget | sufficient | full | sufficient / True | 566 / 999 |
| starlette-05 | How should I use TestClient to ensure lifespan runs in tests? | within_budget | sufficient | full | sufficient / True | 761 / 999 |
| starlette-06 | Какая сигнатура BackgroundTask добавляет одну фоновую задачу к response? | within_budget | sufficient | full | needs_review / True | 709 / 1308 |
| starlette-07 | If one BackgroundTasks function raises an exception, what happens to later tasks and their ordering? Also identify the exact value chosen in our private production deployment. | partial | needs_review | control | needs_review / not_positive | 553 / 1308 |
| starlette-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production starlette deployment? | unanswerable | insufficient | control | needs_review / not_positive | 207 / 1308 |
| starlette-09 | Which starlette configuration is best for our service? Our workload and deployment constraints are not specified. | ambiguous | insufficient | control | needs_review / not_positive | 211 / 1304 |
| starlette-10 | Provide every documented workflow, caveat and complete code example verbatim from all starlette source files in this snapshot, without omissions. | over_budget | insufficient | control | needs_review / not_positive | 214 / 999 |
| typer-01 | Does raising typer.Exit() itself imply an error, and what is its default exit code? | within_budget | sufficient | full | sufficient / True | 781 / 787 |
| typer-02 | Как через typer.Exit сообщить терминалу об ошибке? | within_budget | sufficient | full | sufficient / True | 795 / 787 |
| typer-03 | What visible message distinguishes aborting a Typer program from a normal Exit? | within_budget | sufficient | full | sufficient / True | 781 / 860 |
| typer-04 | How do I give a boolean option alternative positive and negative names such as --accept and --reject? | within_budget | sufficient | full | sufficient / True | 799 / 981 |
| typer-05 | Как записать только отрицательное имя boolean option: важен ли пробел перед /? | within_budget | insufficient | none | needs_review / False | 281 / 947 |
| typer-06 | What happens to --no-force when I declare only the --force option? | within_budget | sufficient | full | sufficient / True | 780 / 947 |
| typer-07 | Does raising typer.Exit() itself imply an error, and what is its default exit code? Also identify the exact value chosen in our private production deployment. | partial | needs_review | control | needs_review / not_positive | 784 / 945 |
| typer-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production typer deployment? | unanswerable | insufficient | control | needs_review / not_positive | 206 / 1018 |
| typer-09 | Which typer configuration is best for our service? Our workload and deployment constraints are not specified. | ambiguous | insufficient | control | needs_review / not_positive | 210 / 908 |
| typer-10 | Provide every documented workflow, caveat and complete code example verbatim from all typer source files in this snapshot, without omissions. | over_budget | insufficient | control | needs_review / not_positive | 213 / 787 |
| uv-01 | Does uv read pip.conf or PIP_INDEX_URL? | within_budget | sufficient | full | sufficient / True | 779 / 1398 |
| uv-02 | В каких двух случаях uv принимает pre-release версии по умолчанию? | within_budget | sufficient | full | needs_review / False | 796 / 1294 |
| uv-03 | What can I do when dependency resolution fails due to a transitive pre-release? | within_budget | sufficient | full | needs_review / True | 775 / 1315 |
| uv-04 | How does uv restrict candidate versions across multiple indexes and why? | within_budget | sufficient | full | needs_review / True | 765 / 1632 |
| uv-05 | Compare first-match, unsafe-first-match and unsafe-best-match index strategies. | within_budget | sufficient | full | needs_review / True | 795 / 2005 |
| uv-06 | Which build isolation mode does uv use by default and what is the escape hatch for a missing build dependency? | within_budget | needs_review | full | needs_review / True | 794 / 722 |
| uv-07 | Does uv read pip.conf or PIP_INDEX_URL? Also identify the exact value chosen in our private production deployment. | partial | needs_review | control | needs_review / not_positive | 793 / 1697 |
| uv-08 | What is the guaranteed 99th-percentile latency in milliseconds for our production uv deployment? | unanswerable | insufficient | control | needs_review / not_positive | 210 / 2005 |
| uv-09 | Which uv configuration is best for our service? Our workload and deployment constraints are not specified. | ambiguous | insufficient | control | needs_review / not_positive | 210 / 665 |
| uv-10 | Provide every documented workflow, caveat and complete code example verbatim from all uv source files in this snapshot, without omissions. | over_budget | needs_review | control | needs_review / not_positive | 786 / 1152 |

## Семантические исключения scorer

### mkdocs-06
Оба ограничения (block/multiline cells и blank lines) видны в двух отдельных цитатах. Frozen witness требует одну contiguous строку.
Evidence IDs: `ev-9b17044532ddadd8`, `ev-dfcd81827c6df16e`.

### uv-06
Вопрос требует default build isolation и preinstall build dependencies. Оба факта видны; specific code example из gold вопрос не запрашивает.
Evidence IDs: `ev-c002f69df094246b`, `ev-4928b1add037a7a4`.

### typer-05
Отсутствует space-before-slash rule, нет источников в packet.
Evidence IDs: .

