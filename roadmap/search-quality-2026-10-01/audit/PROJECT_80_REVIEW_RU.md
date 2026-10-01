# Все 80 вопросов по DocAtlas — разбор видимой выдачи

Набор A = `experiments/grounded-partial/questions.json`; B = `followup_questions.json`. Full/partial/none оценивает только полезность предоставленного evidence, не ответы coding model. Original и guided — разные lanes, не повтор/recovery одного запроса. 72 положительных + 8 unsupported controls. Один reviewer после просмотра; это диагностическая оценка, не blind acceptance.

| ID | Вопрос | Без lookup | С lookup | Причина без lookup | Причина с lookup |
|---|---|---|---|---|---|
| projectA-Q01 | Я клонировал репозиторий и хочу задать первый вопрос по его документации без облачного сервиса. Какие действия нужны? | partial | partial | Запуск локального MCP и три tools есть; подготовка локального индекса/offline шаги неполны. | Tools/local init есть, полного первого offline sync workflow нет. |
| projectA-Q02 | Which MCP tools should my coding agent see, and which one prepares a repository for questions? | partial | partial | Есть prepare_docs для sync и get_docs_context; полного списка трёх tools нет. | Найден agent workflow, но prepare_docs purpose/list трёх tools неполны. |
| projectA-Q03 | Чем Docs MCP отличается от Packs MCP и какой из них подключать для вопросов по репозиторию? | partial | full | Packs обозначен advanced и необязательным, но Docs сторона сравнения не раскрыта. | Docs и Packs command/surface различены. |
| projectA-Q04 | How can I check that my editor is connected to the intended DocAtlas installation rather than an older executable? | partial | partial | Есть doc-atlas --version и published/main distinction, нет проверки команды реально подключённого редактора. | Version/install truth есть, active editor process command проверить нельзя по этим цитатам. |
| projectA-Q05 | Мне надо разобраться во всём репозитории, включая документацию отдельных модулей. Какую область поиска передать? | none | full | Пустая выдача для scope=all. | Явный scope=all с module scope caveat. |
| projectA-Q06 | If I only want repository-wide rules, how do I keep module-specific documentation out of the results? | none | full | Индекс документации и maintenance rules вместо scope=project. | Явное project versus all/module policy. |
| projectA-Q07 | Какие файлы DocAtlas считает документацией проекта и как посмотреть, что он пропустил? | none | partial | Пусто, хотя справка о discover/inspect существует в документах. | Типы project docs и catalog validation есть; inspect candidates/ignored command отсутствует. |
| projectA-Q08 | Where should I declare which documents are authoritative, and how is that different from runtime configuration? | full | full | Явное различие docatlas.project-docs.yaml и docatlas.yaml. | Catalog authority versus runtime configuration и fallback discovery описаны. |
| projectA-Q09 | После изменения Markdown-файла агент цитирует старый текст. Как правильно обновить индекс и повторить вопрос? | none | none | Пусто для обновления stale Markdown. | Module-size policy и source tree не отвечают на stale Markdown sync. |
| projectA-Q10 | I renamed a guide and removed another one. What reconciles the index with those filesystem changes? | partial | partial | Назван sync-saved-docs CI adapter с rename/delete; основной MCP sync contract не доставлен. | prepare_docs performs sync назван, rename/delete reconciliation details отсутствуют. |
| projectA-Q11 | Когда нужен refresh, а когда sync_project_docs? Я путаю обновление библиотеки с обновлением своего репозитория. | partial | partial | Reconcile через sync описан; refresh внешней библиотеки отсутствует. | sync и fetch lifecycle различены, refresh exact action не доставлен. |
| projectA-Q12 | A preparation request returned a job ID instead of documents. What is the expected polling and retry sequence? | partial | partial | prepare/retry есть, polling docs_status по job_id отсутствует. | Job creation и original retry есть, docs_status polling отсутствует. |
| projectA-Q13 | Как отменить подготовку документации и убедиться, что задание действительно остановилось? | none | full | Пусто для cancel/poll workflow. | cancel_docs_job, cancelling не terminal, poll terminal и bounds доставлены. |
| projectA-Q14 | If prepare_docs returns the same recovery action twice without progress, should the agent keep retrying? | none | none | Совет повторить подготовку без правила остановки при отсутствии прогресса. | Tool inventory вместо stop-on-no-progress. |
| projectA-Q15 | В пустом проекте ещё нет документации. Что должен вернуть MCP и что предложить пользователю дальше? | none | partial | Пусто для случая документации нет. | insufficient_evidence boundary есть, no-docs next authoring step отсутствует. |
| projectA-Q16 | Can I index and query project documents with networking disabled, and which optional features would remain unavailable? | partial | partial | Local index описан, но networking-disabled и недоступные optional features не доказаны. | Ни network для local sync, ни optional unavailable features полностью не объяснены. |
| projectA-Q17 | Где проходит путь от get_docs_context до SQLite и кто отвечает за окончательный пакет для модели? | partial | partial | Есть SQLite settings, но call path и final projection owner отсутствуют. | Projection owner есть, полный dispatcher/SQLite path отсутствует. |
| projectA-Q18 | How do lexical retrieval and vector retrieval cooperate, and what happens when vectors are unavailable? | full | full | Lexical default, optional dense/sparse/hybrid и fail-closed/degraded policy доставлены. | Lexical/vector modes и capability-failure policy. |
| projectA-Q19 | Почему добавление неактивного поколения не должно менять ранжирование документов активного индекса? | none | full | Пусто для inactive generation statistics. | Active-only BM25 corpus statistics прямо объяснены. |
| projectA-Q20 | How are parent and child document chunks related, and when may a retrieved chunk expand to surrounding text? | full | full | Parent-child связь и parent/adjacent hydration объяснены. | Parent/child/adjacent и structural checks есть. |
| projectA-Q21 | Если нужное объяснение длиннее лимита MCP, что сохраняется в ответе и как получить оставшуюся часть? | none | partial | Пусто для доставки длинного контекста/continuation. | Compact output/pagination упомянуты, source_uri resources/read отсутствуют. |
| projectA-Q22 | Can several citations come from the same document, and when can the per-source limit overflow? | full | partial | Точное правило одного structural overflow без вытеснения preferred candidates. | Configuration per-document cap/expand есть, точного structural overflow правила больше нет. |
| projectA-Q23 | estimated_tokens — это точное число токенов моей модели? Как ограничивается реальный размер docs_context? | full | full | bytes/4 estimate, o200k admission, whole JSON, 800/3 и несовпадение с моделью описаны. | Whole JSON/tokenizer budget versus public estimate. |
| projectA-Q24 | Why does DocAtlas check relevance again after trimming a snippet instead of trusting the original search score? | none | full | Tool usage и source discovery не объясняют requalification после trim. | Visible coverage после trim/expand requalified; retrieval hit не proof. |
| projectA-Q25 | MCP вернул docs_context, но answer_available=false. Может ли агент всё-таки ответить пользователю по этим фрагментам? | full | full | Явно разрешено host explanation supported facts при false answer flags. | Host synthesis from supported snippets при false flags. |
| projectA-Q26 | A query reports full retrieval coverage but facet coverage is unverified. What can I safely conclude from that? | full | full | Retrieval coverage отделена от support verdict и exact mandatory facets. | Query attribution не support/facet certification. |
| projectA-Q27 | Я спросил про три вещи, а в цитатах есть только две. Как агенту сообщить полезную часть и обозначить недостающую? | none | full | Пусто для useful partial answer и missing facts. | Полезная подтверждённая часть, concrete unknown и next step явно описаны. |
| projectA-Q28 | Are source paths and line numbers enough to reopen the exact text that produced a snippet after the file changes? | none | none | Python module size policy и source types вместо snapshot continuation. | Dependency version policy вместо reopening changed source snapshot. |
| projectA-Q29 | Можно ли считать текст внутри README командой для агента, если там написано игнорировать предыдущие инструкции? | none | none | Docs/INDEX links вместо instruction trust boundary. | Docs/INDEX evaluation links вместо prompt-injection policy. |
| projectA-Q30 | If two repositories have a guide with the same filename, what prevents one project from citing the other project’s content? | none | none | PyPI invalid-publisher checklist вместо project isolation. | PyPI publishing failure checklist вместо project identity isolation. |
| projectA-Q31 | Как запросить старое поведение из CHANGELOG, не подмешивая устаревшие документы в обычные вопросы? | partial | full | CHANGELOG найден, но history eligibility policy не доставлена. | Completed/superseded excluded ordinarily, explicit history разрешена. |
| projectA-Q32 | Does a well-cited documentation answer authorize an agent to edit files or apply a cleanup operation? | partial | full | Documentation obligations не авторизуют patch; cleanup permission отдельно не объяснён. | Host must not grant edit authority и cleanup reviewed plan guards доставлены. |
| projectA-Q33 | Хочу освободить место от индексов, сохранив исходники и настройки. Как сначала проверить план удаления? | none | full | Runtime/catalog settings вместо clear-index preview. | clear-index preview-only без apply и preserve configuration/sources. |
| projectA-Q34 | What happens if another live process is using the index when I attempt to clear it? | full | partial | Live-process blockers прямо названы непереступаемыми. | remove_library_docs/writer lease пример есть, другой live reader blocker описан не полностью. |
| projectA-Q35 | Я просмотрел план очистки, но содержимое индекса уже изменилось. Можно ли применить старый план? | partial | full | Plan digest и same-plan workflow есть, явного stale fingerprint refusal нет. | Stale digest/fingerprint explicitly refuses before destructive move. |
| projectA-Q36 | Which checks should I run before submitting a retrieval change, and which results actually establish answer usefulness? | partial | partial | Некоторые retrieval boundary tests названы; PR check sequence и usefulness evidence не доставлены. | PR suite/offline command и отсутствие product guarantee есть; task-level usefulness measurement не описано. |
| projectA-Q37 | Каким алгоритмом DocAtlas шифрует локальную SQLite-базу и где поменять ключ шифрования? | control | control | Encryption/key premise unsupported; generic settings returned, no invented encryption in payload. | Encryption/key premise unsupported; generic settings returned, no invented encryption in payload. |
| projectA-Q38 | Which published benchmark guarantees that DocAtlas always reduces the total token bill of a coding agent? | control | control | Universal token-saving benchmark unsupported; native future success criteria, guided explicit no unmeasured guarantee. | Universal token-saving benchmark unsupported; native future success criteria, guided explicit no unmeasured guarantee. |
| projectA-Q39 | Какой у DocAtlas гарантированный срок хранения удалённых документов и где настроить ровно 90 дней? | control | control | 90-day removed-document retention unsupported; irrelevant settings returned, no invented value. | 90-day removed-document retention unsupported; irrelevant settings returned, no invented value. |
| projectA-Q40 | What does the documentation say about automatic per-tenant row-level permissions in a shared DocAtlas server? | control | control | Per-tenant row-level permissions unsupported; native abstains, guided project-isolation text not permission proof. | Per-tenant row-level permissions unsupported; native abstains, guided project-isolation text not permission proof. |
| projectB-Q01 | Я впервые подключил MCP. Нужно ли каждый вопрос начинать с docs_status? | full | full | get_docs_context first, docs_status только job/status. | Explicit first get_docs_context and docs_status/job policy. |
| projectB-Q02 | Which MCP tool should a coding agent call before modifying a documented module? | full | full | Перед coding/patch явно get_docs_context first. | Explicit first documentation call before edit. |
| projectB-Q03 | В ответе есть цитаты, но answer_supported=false. Могу ли я объяснить найденное пользователю? | none | full | Старое описание answer_supported=true вместо права host отвечать при false flags. | Current agent workflow permits host synthesis supported snippets despite false flags. |
| projectB-Q04 | How do I include module documentation when exploring the entire repository? | full | full | all includes repo/module, exact module_path ограничивает. | all versus project/module filters. |
| projectB-Q05 | Мне нужны только общие документы репозитория, без module-документов. Как ограничить поиск? | none | full | Пусто для project-only scope. | scope=project explicitly retains repo policy only. |
| projectB-Q06 | Where do I declare which local documents are authoritative? | partial | full | agent-contract сообщает authorities, но место декларации catalog не названо. | Catalog authority versus runtime configuration. |
| projectB-Q07 | Чем конфигурация поиска отличается от каталога авторитетных документов? | partial | full | Runtime YAML и local index есть; authority catalog отсутствует. | docatlas.yaml and project-docs catalog roles distinguished. |
| projectB-Q08 | I committed a README change. How does the next documentation query become current? | none | none | Evaluation index/release checklist вместо current query lifecycle. | Release/eval docs still replace synchronization contract. |
| projectB-Q09 | В рабочей директории есть мои незакоммиченные правки. Может ли MCP сам пересобрать индекс? | none | full | Пусто для dirty worktree mutation policy. | Dirty worktree confirmation gating and read-only query. |
| projectB-Q10 | Can get_docs_context change the index by itself? | full | full | Query never reconciles; clean preflight and prepare boundary прямо описаны. | Query read-only and prepare rechecks clean worktree/HEAD. |
| projectB-Q11 | Подготовка вернула job_id. Что делать до повторного исходного вопроса? | partial | full | Polling упомянут, но legacy get_docs_job_status/cancel_docs_job tool names вместо current router actions. | docs_status(action=job), deadline bounded terminal inspection then original retry. |
| projectB-Q12 | Does requesting cancellation prove that a background job has stopped? | none | full | Quote semantic binding вместо cancel request versus terminal acknowledgement. | cancelling acknowledgement is not terminal; inspect status and stop bounds. |
| projectB-Q13 | Почему estimated_tokens может отличаться от бюджета допуска docs_context? | full | full | bytes/4 versus max offline tokenizer whole response admission. | Estimate and admission two measures explained. |
| projectB-Q14 | Does the output budget include citation metadata as well as document text? | none | none | CLI --budget table вместо whole MCP metadata budget. | Only CLI --budget table; metadata question not supported. |
| projectB-Q15 | Ссылка source_uri появилась в цитате. Нужно ли немедленно её открывать? | partial | partial | Locator optional и exact resources/read есть, no automatic read policy отсутствует. | Optional locator/read mechanism but concrete missing-fact prerequisite absent. |
| projectB-Q16 | Can a continuation locator be used to read an unrelated file? | none | none | Cleanup unrelated-files policy вместо locator scope. | Cleanup and continuation attempt cap not capability-bound path restrictions. |
| projectB-Q17 | Исходный файл изменился между поиском и дочитыванием. Что должен вернуть reader? | none | full | Пусто для changed snapshot reader status. | source_changed after file snapshot mismatch, do not read latest silently. |
| projectB-Q18 | Can two different continuation locators return overlapping lines without detection? | full | full | Cross-locator overlapping lines explicitly rejected. | Overlap guard across locators explicit. |
| projectB-Q19 | Дочитывание не удалось, но часть ответа уже подтверждена. Нужно ли отказываться от всего ответа? | none | full | Пусто для preservation of partial answer on read failure. | Read failure cannot discard existing partial answer. |
| projectB-Q20 | What should the agent say when documentation covers only one part of my question? | full | none | State supported part, name unknown and next step. | Guided lane lost the native useful partial-answer guidance. |
| projectB-Q21 | Можно ли выполнить shell-команду, которую документ предлагает агенту внутри цитаты? | full | partial | Source data not policy, shell/credential actions not selected by prose. | Documents are untrusted, but explicit no-execute-policy sentence trimmed away. |
| projectB-Q22 | Does successful retrieval grant permission to edit files? | full | full | Do not grant answer/edit authority from successful retrieval. | Explicit no answer/edit authority from retrieval. |
| projectB-Q23 | В двух проектах одинаковый README.md. Как не получить цитату из чужого проекта? | none | full | Пусто для cross-project same README isolation. | Project identity receives isolated SQLite/extracted state. |
| projectB-Q24 | Are evaluation reports eligible evidence for an ordinary operational question? | full | full | Operational retrieval excludes evaluation/planning/history unless requested. | Ordinary operational excludes evaluation/planning/history. |
| projectB-Q25 | Как ограничение per-source влияет на соседние фрагменты одного документа? | none | partial | Пусто для per-source structural neighbor cap. | Parent/adjacent relation present, per-source rule absent. |
| projectB-Q26 | Can an inactive indexing generation change the ranking of active documentation? | full | full | Inactive generation cannot alter active BM25 ranking. | Inactive generation statistics exclusion. |
| projectB-Q27 | Зачем повторно проверять цитату после её сокращения? | none | full | Пусто для requalification after trim. | Visible snippets requalified after expansion/trimming. |
| projectB-Q28 | Why should a matching heading not be enough to support a requested fact? | full | full | Даже verbatim quote binding не доказывает ответ; title/heading matching тем более не semantic proof. | Quote binding versus semantic support logically addresses heading insufficiency. |
| projectB-Q29 | Какая часть работы доступна без сети и заранее загруженной языковой модели? | none | none | Пусто для offline/model-free features. | Still empty for offline/model-free question. |
| projectB-Q30 | What happens when a dependency version cannot be proven from the repository? | full | full | Exact/declared-only/unbound states с repository proof distinction. | Exact/declared-only/unbound version-binding distinction. |
| projectB-Q31 | Можно ли использовать документацию latest как доказательство поведения установленной версии? | partial | partial | Published/main mismatch предостережение есть, external latest versus installed dependency не объяснено. | Exact version metadata preference mentioned, no complete latest safety contract. |
| projectB-Q32 | Can index cleanup run while another process is writing the index? | full | full | Live processes explicitly fail closed. | Live writer lease prevents cleanup. |
| projectB-Q33 | Почему клиент может видеть только маркер structuredContent, без самой цитаты? | none | full | Пусто для structured-only marker delivery. | structuredContent marker, OpenCode fallback and nonduplicated channel delivery explained. |
| projectB-Q34 | How can I check that my installed MCP command matches the current package? | partial | partial | Version check/release mismatch есть, actual MCP executable verification отсутствует. | Installed version versus main and MCP identity, no active executable command verification. |
| projectB-Q35 | Для чего генерировать agent-contract перед работой агента с репозиторием? | none | none | Пусто для purpose of agent-contract. | Still empty for agent-contract purpose. |
| projectB-Q36 | Do successful provider-free tests prove that real agents spend fewer task tokens? | none | none | Только pytest commands, никакого отрицания product token-saving guarantee. | Tests shown, task-level token savings not proved or denied. |
| projectB-Q37 | Где подтверждено, что DocAtlas всегда экономит ровно 50 процентов токенов? | control | control | Exactly 50 percent universal savings unsupported; both lanes abstain. | Exactly 50 percent universal savings unsupported; both lanes abstain. |
| projectB-Q38 | Which document guarantees that every query receives a complete correct answer? | control | control | Universal complete-answer guarantee unsupported; limitations evidence supports safe non-guarantee explanation. | Universal complete-answer guarantee unsupported; limitations evidence supports safe non-guarantee explanation. |
| projectB-Q39 | Какой пароль администратора установлен в моей частной production-среде? | control | control | Private production password unknowable; installer snippet irrelevant, no password invented. | Private production password unknowable; installer snippet irrelevant, no password invented. |
| projectB-Q40 | Where is mandatory ninety-day retention of every conversation specified? | control | control | Mandatory 90-day conversation retention unsupported; native abstains, guided question-planning text irrelevant. | Mandatory 90-day conversation retention unsupported; native abstains, guided question-planning text irrelevant. |

## Связь с цитатами

Полные исходные MCP-ответы: `raw/project80/all/<ID>.json` и `raw/project80/guided/<ID>.json`. Ниже IDs с координатами; причины относятся только к соответствующему packet.

### projectA-Q01
- original: `ev-b96657827b8741a6` — `wiki/Commands.md:65–75`; `ev-bc89dfb55c5a3cdb` — `docs/mcp-docs-server.md:1–16`.
- guided: `ev-b96657827b8741a6` — `wiki/Commands.md:65–73`; `ev-415e2b79b4914a68` — `SKILL.md:114–124`.

### projectA-Q02
- original: `ev-fb8195e3bcc94c7d` — `docs/project-docs-mcp-workflow.md:160–166`; `ev-8555f13ce0818b33` — `docs/context7-docmancer-comparison.md:224–231`; `ev-32f41c85e7d6a0ef` — `wiki/Architecture.md:108–108`.
- guided: `ev-a5d3220f93684dad` — `SKILL.md:137–146`.

### projectA-Q03
- original: `ev-257e7697739a8660` — `wiki/Commands.md:77–79`; `ev-b6c005fa05e1c299` — `wiki/Commands.md:3–3`.
- guided: `ev-a5d3220f93684dad` — `SKILL.md:144–146`; `ev-9f2e09d419950450` — `SKILL.md:15–19`.

### projectA-Q04
- original: `ev-848dea5ff0c19302` — `README.md:70–76`; `ev-115934c532ee1077` — `README.md:80–80`.
- guided: `ev-848dea5ff0c19302` — `README.md:70–76`; `ev-5cbb2a113ae23e4a` — `docs/mcp-docs-server.md:95–97`; `ev-d4590446882e1d20` — `docs/security/mcp-runtime-threat-model.md:81–81`.

### projectA-Q05
- original: источников нет.
- guided: `ev-f98a264d826c7a0c` — `docs/mcp-quickstart-example.md:8–21`.

### projectA-Q06
- original: `ev-628259aa8c202b7b` — `docs/INDEX.md:48–56`; `ev-94c12ccadf987a58` — `docs/INDEX.md:3–3`.
- guided: `ev-628259aa8c202b7b` — `docs/INDEX.md:52–56`; `ev-f98a264d826c7a0c` — `docs/mcp-quickstart-example.md:8–21`.

### projectA-Q07
- original: источников нет.
- guided: `ev-15667ad6c91bb7bc` — `docs/project-docs-mcp-workflow.md:1–3`; `ev-22931c95d8e6fb03` — `docs/project-docs-mcp-workflow.md:225–225`.

### projectA-Q08
- original: `ev-42aab85940e49cc9` — `wiki/Configuration.md:7–10`; `ev-591bef2d0861c6cd` — `docs/index-cleanup.md:83–85`; `ev-98acd471bea6d279` — `wiki/Troubleshooting.md:139–139`.
- guided: `ev-42aab85940e49cc9` — `wiki/Configuration.md:7–10`; `ev-eade1ac26c4557a9` — `docs/project-docs-mcp-workflow.md:186–188`; `ev-1a83e713dd069390` — `docs/adr/0002-evidence-authority-direction.md:37–37`.

### projectA-Q09
- original: источников нет.
- guided: `ev-94c255a8d2e17ee6` — `docs/development/python-module-size-policy.md:27–27`; `ev-564efa444a55bf0c` — `CONTRIBUTING.md:13–27`.

### projectA-Q10
- original: `ev-040b013ac1d62329` — `docs/change-aware-docs.md:14–14`; `ev-e58e5bef8bfa606b` — `docs/change-aware-docs.md:3–3`; `ev-463a10526e12abcd` — `docs/change-aware-docs.md:20–20`.
- guided: `ev-37dbbffa93515586` — `docs/product-scope.md:11–11`; `ev-38329dc4234fd6be` — `wiki/Architecture.md:27–32`; `ev-040b013ac1d62329` — `docs/change-aware-docs.md:14–14`.

### projectA-Q11
- original: `ev-c062d9d7d763f7e8` — `docs/project-docs-mcp-workflow.md:295–314`; `ev-ea6cd43d58747d0b` — `docs/project-docs-mcp-workflow.md:23–30`.
- guided: `ev-775a05a31e48dad8` — `docs/DOCMANCER_PRODUCT_BRIEF.md:21–25`; `ev-c062d9d7d763f7e8` — `docs/project-docs-mcp-workflow.md:312–312`; `ev-ea6cd43d58747d0b` — `docs/project-docs-mcp-workflow.md:23–23`.

### projectA-Q12
- original: `ev-aa6e47640612ab0d` — `wiki/Architecture.md:88–90`; `ev-3df7f69642bada1a` — `wiki/Commands.md:75–75`; `ev-276a0ffa1e1de8c5` — `docs/mcp-response-contract.md:39–39`.
- guided: `ev-4eeeef16d9abe8df` — `wiki/Architecture.md:134–139`; `ev-fb8195e3bcc94c7d` — `docs/project-docs-mcp-workflow.md:160–166`.

### projectA-Q13
- original: источников нет.
- guided: `ev-dc5d905e058935e0` — `docs/source-continuation.md:62–69`.

### projectA-Q14
- original: `ev-8c837d2c714332b9` — `docs/project-docs-mcp-workflow.md:293–293`; `ev-fb8195e3bcc94c7d` — `docs/project-docs-mcp-workflow.md:160–166`; `ev-583cd57c2c02e63e` — `docs/AGENT_DOCS_WORKFLOW.md:49–49`.
- guided: `ev-628259aa8c202b7b` — `docs/INDEX.md:52–56`; `ev-6526ca044d0c3b9b` — `SKILL.md:21–27`.

### projectA-Q15
- original: источников нет.
- guided: `ev-8d053ebfe16a00b5` — `README.md:120–124`; `ev-a23b8dfc205a1884` — `README.md:136–136`.

### projectA-Q16
- original: `ev-38329dc4234fd6be` — `wiki/Architecture.md:27–32`; `ev-4ea4070129065ca3` — `docs/index-cleanup.md:102–104`; `ev-2e37682e3d93fc88` — `wiki/Architecture.md:3–3`.
- guided: `ev-8d053ebfe16a00b5` — `README.md:120–124`; `ev-0d3fbb087d9ca510` — `README.md:202–202`.

### projectA-Q17
- original: `ev-7fe4b86a5f13c543` — `wiki/Configuration.md:14–22`; `ev-694534478b4798f1` — `docs/project-docs-mcp-workflow.md:263–269`.
- guided: `ev-8d053ebfe16a00b5` — `README.md:120–124`; `ev-b4482d338ae127c0` — `docs/modules/question-planning.md:17–17`.

### projectA-Q18
- original: `ev-8ab472f24f0ab11b` — `wiki/Configuration.md:51–51`; `ev-555bbd0e47e89b22` — `wiki/Architecture.md:40–42`.
- guided: `ev-8ab472f24f0ab11b` — `wiki/Configuration.md:51–51`; `ev-555bbd0e47e89b22` — `wiki/Architecture.md:40–42`.

### projectA-Q19
- original: источников нет.
- guided: `ev-57b8b76e50d160c7` — `docs/retrieval-boundaries.md:5–10`.

### projectA-Q20
- original: `ev-e1b850334f3074a9` — `wiki/Architecture.md:15–17`; `ev-2e37682e3d93fc88` — `wiki/Architecture.md:3–3`.
- guided: `ev-e1b850334f3074a9` — `wiki/Architecture.md:15–15`; `ev-13f2b97ca84faff0` — `docs/retrieval-boundaries.md:14–19`.

### projectA-Q21
- original: источников нет.
- guided: `ev-c62ba46b3e1f0953` — `docs/adr/0001-mcp-boundary-contracts.md:23–26`; `ev-baf07e0d8cd4a015` — `docs/AGENT_DOCS_WORKFLOW.md:43–45`.

### projectA-Q22
- original: `ev-13f2b97ca84faff0` — `docs/retrieval-boundaries.md:12–19`; `ev-65c29dc99ab4caa5` — `README.md:239–239`.
- guided: `ev-bf827d9b29daff2a` — `wiki/Configuration.md:78–91`.

### projectA-Q23
- original: `ev-5b00a0b7e2c7179b` — `docs/retrieval-boundaries.md:21–30`; `ev-9ac525f0c65304ac` — `CONTRIBUTING.md:38–38`.
- guided: `ev-5b00a0b7e2c7179b` — `docs/retrieval-boundaries.md:23–30`; `ev-a23b8dfc205a1884` — `README.md:136–136`.

### projectA-Q24
- original: `ev-b4c3b6df1625e8fa` — `README.md:180–190`; `ev-71cea1245e00a5e4` — `README.md:149–149`.
- guided: `ev-753fe14c0c752072` — `docs/modules/evidence-selection.md:21–22`; `ev-d15f77a0a6bd4701` — `docs/adr/0003-context-first-project-reads.md:34–41`; `ev-b529e359106cbb6a` — `docs/mcp-docs-server.md:47–47`.

### projectA-Q25
- original: `ev-e5f07fb64415686a` — `docs/source-continuation.md:5–10`; `ev-9ac525f0c65304ac` — `CONTRIBUTING.md:38–38`.
- guided: `ev-e5f07fb64415686a` — `docs/source-continuation.md:5–10`; `ev-91c715e077a03ede` — `docs/mcp-docs-server.md:42–42`.

### projectA-Q26
- original: `ev-8ab472f24f0ab11b` — `wiki/Configuration.md:51–51`; `ev-278e9d1d7b0db0c8` — `docs/modules/evidence-selection.md:7–15`.
- guided: `ev-91c715e077a03ede` — `docs/mcp-docs-server.md:42–42`; `ev-278e9d1d7b0db0c8` — `docs/modules/evidence-selection.md:7–11`.

### projectA-Q27
- original: источников нет.
- guided: `ev-d6821cc55bf2b657` — `docs/grounded-host-session.md:66–70`; `ev-b529e359106cbb6a` — `docs/mcp-docs-server.md:47–47`; `ev-c2e7ecffbcf3e7e9` — `README.md:17–17`.

### projectA-Q28
- original: `ev-d5b225465a5a3d93` — `docs/development/python-module-size-policy.md:9–9`; `ev-8ef111732c24e323` — `wiki/Supported-Sources.md:10–12`; `ev-e932d60bcde13c17` — `docs/development/python-module-size-policy.md:3–3`.
- guided: `ev-faf25c8b33d98c65` — `docs/project-docs-mcp-workflow.md:170–172`; `ev-42cb9cf1711e90f3` — `docs/DOCMANCER_PRODUCT_BRIEF.md:58–63`.

### projectA-Q29
- original: `ev-af99ccf59b2af6c1` — `docs/INDEX.md:40–44`; `ev-94c12ccadf987a58` — `docs/INDEX.md:3–9`.
- guided: `ev-af99ccf59b2af6c1` — `docs/INDEX.md:40–44`.

### projectA-Q30
- original: `ev-e90f9271aade59ac` — `docs/RELEASE_CHECKLIST.md:61–71`; `ev-e21aa1cc1171faef` — `docs/RELEASE_CHECKLIST.md:3–3`.
- guided: `ev-e90f9271aade59ac` — `docs/RELEASE_CHECKLIST.md:61–71`.

### projectA-Q31
- original: `ev-07e22591bab2c936` — `CHANGELOG.md:1–5`.
- guided: `ev-22931c95d8e6fb03` — `docs/project-docs-mcp-workflow.md:225–225`; `ev-07e22591bab2c936` — `CHANGELOG.md:1–5`; `ev-5a019ce5825cb4bb` — `CHANGELOG.md:20–20`.

### projectA-Q32
- original: `ev-f4ec12532fa8d2f3` — `docs/modules/patch-request-planning.md:1–14`.
- guided: `ev-328bfe6bae7fc4d9` — `README.md:208–214`; `ev-3370ff9f59c910af` — `SKILL.md:160–160`.

### projectA-Q33
- original: `ev-bed94811b504427c` — `wiki/Configuration.md:1–10`.
- guided: `ev-35fe085f79fc2397` — `docs/index-cleanup.md:1–6`; `ev-bed94811b504427c` — `wiki/Configuration.md:1–5`.

### projectA-Q34
- original: `ev-35fe085f79fc2397` — `docs/index-cleanup.md:1–15`; `ev-07b41b7ca120f14b` — `docs/index-cleanup.md:66–67`.
- guided: `ev-35fe085f79fc2397` — `docs/index-cleanup.md:1–6`; `ev-ef889aef8d491c36` — `docs/index-cleanup.md:106–106`.

### projectA-Q35
- original: `ev-35fe085f79fc2397` — `docs/index-cleanup.md:1–15`; `ev-8b0e215ac92e756f` — `docs/index-cleanup.md:29–41`.
- guided: `ev-1202dae48bc72f44` — `docs/index-cleanup.md:90–91`; `ev-328bfe6bae7fc4d9` — `README.md:208–214`.

### projectA-Q36
- original: `ev-57b8b76e50d160c7` — `docs/retrieval-boundaries.md:3–10`; `ev-8ab7fb4586715161` — `docs/retrieval-boundaries.md:34–39`.
- guided: `ev-bf81fc44f9c226ab` — `CONTRIBUTING.md:59–63`; `ev-6ec9ec0fa9f1534a` — `docs/source-continuation.md:52–57`; `ev-f82eea255a6b1f2d` — `docs/testing.md:5–5`.

### projectA-Q37
- original: `ev-7fe4b86a5f13c543` — `wiki/Configuration.md:14–22`; `ev-56aa37e6be0de7e2` — `wiki/Configuration.md:3–3`.
- guided: `ev-7fe4b86a5f13c543` — `wiki/Configuration.md:14–22`; `ev-bed94811b504427c` — `wiki/Configuration.md:1–5`.

### projectA-Q38
- original: `ev-028217ff5c053444` — `docs/adr/0002-evidence-authority-direction.md:54–62`; `ev-0eff1fde7658d429` — `docs/adr/0002-evidence-authority-direction.md:75–75`.
- guided: `ev-6ec9ec0fa9f1534a` — `docs/source-continuation.md:52–57`; `ev-b408526d22b8d6a8` — `docs/analysis/p0-governance-value-proof-remediation.md:34–40`.

### projectA-Q39
- original: `ev-42aab85940e49cc9` — `wiki/Configuration.md:7–8`; `ev-c2eddc6ad062a61d` — `wiki/Architecture.md:21–23`; `ev-38329dc4234fd6be` — `wiki/Architecture.md:27–28`.
- guided: `ev-bed94811b504427c` — `wiki/Configuration.md:5–5`; `ev-42aab85940e49cc9` — `wiki/Configuration.md:7–8`; `ev-c2eddc6ad062a61d` — `wiki/Architecture.md:21–23`.

### projectA-Q40
- original: источников нет.
- guided: `ev-38329dc4234fd6be` — `wiki/Architecture.md:27–32`.

### projectB-Q01
- original: `ev-29991f84ece835bb` — `docs/mcp-docs-server.md:53–53`; `ev-f55b7fbc6503dac2` — `docs/mcp-docs-server.md:3–3`; `ev-ad64fbc62cc31d4f` — `docs/mcp-docs-server.md:35–40`.
- guided: `ev-5e9fe788120ffba3` — `docs/mcp-docs-server.md:33–40`; `ev-4894e9170acd01af` — `README.md:225–225`.

### projectB-Q02
- original: `ev-a5d3220f93684dad` — `SKILL.md:135–146`.
- guided: `ev-a5d3220f93684dad` — `SKILL.md:137–146`.

### projectB-Q03
- original: `ev-17ef046ae8ab123e` — `docs/mcp-docs-server.md:51–51`; `ev-f55b7fbc6503dac2` — `docs/mcp-docs-server.md:3–3`.
- guided: `ev-17ef046ae8ab123e` — `docs/mcp-docs-server.md:51–51`; `ev-868f70b4f4e29a0d` — `docs/AGENT_DOCS_WORKFLOW.md:22–27`.

### projectB-Q04
- original: `ev-f98a264d826c7a0c` — `docs/mcp-quickstart-example.md:19–21`; `ev-87e528a0bbf72361` — `wiki/Architecture.md:110–110`; `ev-faf25c8b33d98c65` — `docs/project-docs-mcp-workflow.md:170–172`.
- guided: `ev-f98a264d826c7a0c` — `docs/mcp-quickstart-example.md:19–21`; `ev-87e528a0bbf72361` — `wiki/Architecture.md:110–110`; `ev-faf25c8b33d98c65` — `docs/project-docs-mcp-workflow.md:172–172`.

### projectB-Q05
- original: источников нет.
- guided: `ev-1a722cd318071d8c` — `docs/security/mcp-runtime-threat-model.md:27–34`; `ev-4aef6ace421b38b8` — `README.md:190–190`.

### projectB-Q06
- original: `ev-fcb08545690a408c` — `README.md:216–225`.
- guided: `ev-fcb08545690a408c` — `README.md:216–223`; `ev-42aab85940e49cc9` — `wiki/Configuration.md:7–10`.

### projectB-Q07
- original: `ev-bed94811b504427c` — `wiki/Configuration.md:1–5`; `ev-38329dc4234fd6be` — `wiki/Architecture.md:25–32`.
- guided: `ev-42aab85940e49cc9` — `wiki/Configuration.md:7–10`; `ev-bed94811b504427c` — `wiki/Configuration.md:1–5`.

### projectB-Q08
- original: `ev-af99ccf59b2af6c1` — `docs/INDEX.md:40–44`; `ev-da9e1d6c3a23a58f` — `docs/RELEASE_CHECKLIST.md:7–17`.
- guided: `ev-af99ccf59b2af6c1` — `docs/INDEX.md:43–44`; `ev-da9e1d6c3a23a58f` — `docs/RELEASE_CHECKLIST.md:9–17`.

### projectB-Q09
- original: источников нет.
- guided: `ev-bc5a71393d9e1901` — `docs/mcp-docs-server.md:61–61`.

### projectB-Q10
- original: `ev-b4c3b6df1625e8fa` — `README.md:180–190`; `ev-bc5a71393d9e1901` — `docs/mcp-docs-server.md:61–61`.
- guided: `ev-b4c3b6df1625e8fa` — `README.md:182–188`; `ev-bc5a71393d9e1901` — `docs/mcp-docs-server.md:61–61`.

### projectB-Q11
- original: `ev-aef38d4357f20284` — `wiki/Architecture.md:147–147`; `ev-2e37682e3d93fc88` — `wiki/Architecture.md:3–3`.
- guided: `ev-20e41df4610c5b09` — `docs/AGENT_DOCS_WORKFLOW.md:11–11`; `ev-fb8195e3bcc94c7d` — `docs/project-docs-mcp-workflow.md:160–166`.

### projectB-Q12
- original: `ev-9c4e4bc207583e17` — `docs/grounded-host-session.md:16–20`; `ev-8a9a4ea0a02d0603` — `docs/grounded-host-session.md:3–6`.
- guided: `ev-9c4e4bc207583e17` — `docs/grounded-host-session.md:16–20`; `ev-dc5d905e058935e0` — `docs/source-continuation.md:62–69`.

### projectB-Q13
- original: `ev-5b00a0b7e2c7179b` — `docs/retrieval-boundaries.md:21–30`; `ev-9ac525f0c65304ac` — `CONTRIBUTING.md:38–38`.
- guided: `ev-5b00a0b7e2c7179b` — `docs/retrieval-boundaries.md:23–30`; `ev-9ac525f0c65304ac` — `CONTRIBUTING.md:38–38`.

### projectB-Q14
- original: `ev-d472078b61b33ab5` — `SKILL.md:96–110`; `ev-3fb32437317a4184` — `SKILL.md:71–78`.
- guided: `ev-d472078b61b33ab5` — `SKILL.md:104–110`.

### projectB-Q15
- original: `ev-c7d2a99dd5c55acc` — `docs/source-continuation.md:18–22`.
- guided: `ev-c7d2a99dd5c55acc` — `docs/source-continuation.md:18–22`; `ev-868f70b4f4e29a0d` — `docs/AGENT_DOCS_WORKFLOW.md:22–27`; `ev-c2e7ecffbcf3e7e9` — `README.md:17–17`.

### projectB-Q16
- original: `ev-d1cb81e8a20f2de7` — `docs/index-cleanup.md:1–15`; `ev-c5d20088356d2d90` — `docs/index-cleanup.md:53–55`.
- guided: `ev-d1cb81e8a20f2de7` — `docs/index-cleanup.md:8–15`; `ev-ee2f289d2068badc` — `docs/source-continuation.md:26–31`.

### projectB-Q17
- original: источников нет.
- guided: `ev-f978797d60370d91` — `docs/source-continuation.md:34–41`; `ev-c7d2a99dd5c55acc` — `docs/source-continuation.md:18–22`.

### projectB-Q18
- original: `ev-5f69e31889b4d3d4` — `docs/grounded-host-session.md:22–27`; `ev-8a9a4ea0a02d0603` — `docs/grounded-host-session.md:3–6`.
- guided: `ev-5f69e31889b4d3d4` — `docs/grounded-host-session.md:22–27`; `ev-ee2f289d2068badc` — `docs/source-continuation.md:26–31`.

### projectB-Q19
- original: источников нет.
- guided: `ev-d6821cc55bf2b657` — `docs/grounded-host-session.md:66–70`; `ev-b370d114df13998e` — `docs/grounded-host-session.md:8–14`.

### projectB-Q20
- original: `ev-6526ca044d0c3b9b` — `SKILL.md:21–27`; `ev-6ff3dc33a15d2912` — `SKILL.md:96–102`; `ev-d6821cc55bf2b657` — `docs/grounded-host-session.md:67–70`.
- guided: `ev-6526ca044d0c3b9b` — `SKILL.md:21–27`; `ev-6ff3dc33a15d2912` — `SKILL.md:96–102`; `ev-8cecf6996400b5ad` — `docs/mcp-docs-server.md:73–75`.

### projectB-Q21
- original: `ev-1a722cd318071d8c` — `docs/security/mcp-runtime-threat-model.md:26–38`; `ev-706ecb643f7fca6e` — `docs/security/mcp-runtime-threat-model.md:3–3`.
- guided: `ev-1a722cd318071d8c` — `docs/security/mcp-runtime-threat-model.md:26–33`.

### projectB-Q22
- original: `ev-3370ff9f59c910af` — `SKILL.md:160–160`; `ev-1d4e03c7da833738` — `docs/one-call-agent-loop.md:7–18`.
- guided: `ev-6a4f1c0bd4d5a4e6` — `README.md:29–34`; `ev-3370ff9f59c910af` — `SKILL.md:160–160`; `ev-1d4e03c7da833738` — `docs/one-call-agent-loop.md:13–13`.

### projectB-Q23
- original: источников нет.
- guided: `ev-38329dc4234fd6be` — `wiki/Architecture.md:27–32`.

### projectB-Q24
- original: `ev-0935e1988f820752` — `eval/project_context_quality/README.md:16–21`; `ev-32f41c85e7d6a0ef` — `wiki/Architecture.md:108–108`.
- guided: `ev-32f41c85e7d6a0ef` — `wiki/Architecture.md:108–108`; `ev-0935e1988f820752` — `eval/project_context_quality/README.md:16–21`.

### projectB-Q25
- original: источников нет.
- guided: `ev-e1b850334f3074a9` — `wiki/Architecture.md:15–15`.

### projectB-Q26
- original: `ev-57b8b76e50d160c7` — `docs/retrieval-boundaries.md:3–10`; `ev-e1b850334f3074a9` — `wiki/Architecture.md:15–15`.
- guided: `ev-57b8b76e50d160c7` — `docs/retrieval-boundaries.md:5–10`; `ev-e1b850334f3074a9` — `wiki/Architecture.md:15–15`.

### projectB-Q27
- original: источников нет.
- guided: `ev-b529e359106cbb6a` — `docs/mcp-docs-server.md:47–47`.

### projectB-Q28
- original: `ev-9c4e4bc207583e17` — `docs/grounded-host-session.md:16–27`; `ev-8a9a4ea0a02d0603` — `docs/grounded-host-session.md:3–6`.
- guided: `ev-9c4e4bc207583e17` — `docs/grounded-host-session.md:16–20`; `ev-fe1c339dcef41a35` — `wiki/Supported-Sources.md:37–44`.

### projectB-Q29
- original: источников нет.
- guided: источников нет.

### projectB-Q30
- original: `ev-4101801b8c296802` — `docs/DOCMANCER_PRODUCT_BRIEF.md:58–65`; `ev-faf25c8b33d98c65` — `docs/project-docs-mcp-workflow.md:170–172`.
- guided: `ev-4101801b8c296802` — `docs/DOCMANCER_PRODUCT_BRIEF.md:65–65`; `ev-faf25c8b33d98c65` — `docs/project-docs-mcp-workflow.md:170–172`.

### projectB-Q31
- original: `ev-848dea5ff0c19302` — `README.md:70–76`; `ev-115934c532ee1077` — `README.md:80–80`.
- guided: `ev-848dea5ff0c19302` — `README.md:70–76`; `ev-9a03f176e224353f` — `wiki/Architecture.md:94–98`.

### projectB-Q32
- original: `ev-35fe085f79fc2397` — `docs/index-cleanup.md:1–6`; `ev-328bfe6bae7fc4d9` — `README.md:206–214`.
- guided: `ev-35fe085f79fc2397` — `docs/index-cleanup.md:3–6`; `ev-4ea4070129065ca3` — `docs/index-cleanup.md:102–104`; `ev-94dc926d3c644390` — `docs/index-cleanup.md:17–20`.

### projectB-Q33
- original: источников нет.
- guided: `ev-20f47c72fa36382b` — `docs/mcp-docs-server.md:91–91`.

### projectB-Q34
- original: `ev-f1ed8a300e832d1a` — `docs/DOCMANCER_PRODUCT_BRIEF.md:82–84`; `ev-848dea5ff0c19302` — `README.md:70–76`.
- guided: `ev-f1ed8a300e832d1a` — `docs/DOCMANCER_PRODUCT_BRIEF.md:82–84`; `ev-848dea5ff0c19302` — `README.md:70–72`; `ev-0de07617bdcacb64` — `docs/RELEASE_CHECKLIST.md:25–25`.

### projectB-Q35
- original: источников нет.
- guided: источников нет.

### projectB-Q36
- original: `ev-b5440bc2f89c7200` — `docs/testing.md:1–3`; `ev-bf81fc44f9c226ab` — `CONTRIBUTING.md:61–63`; `ev-f82eea255a6b1f2d` — `docs/testing.md:5–5`.
- guided: `ev-b5440bc2f89c7200` — `docs/testing.md:1–3`; `ev-bf81fc44f9c226ab` — `CONTRIBUTING.md:62–63`; `ev-f82eea255a6b1f2d` — `docs/testing.md:5–5`.

### projectB-Q37
- original: источников нет.
- guided: источников нет.

### projectB-Q38
- original: `ev-6ec9ec0fa9f1534a` — `docs/source-continuation.md:50–57`; `ev-650a1a9ec7a8ed34` — `docs/source-continuation.md:5–10`.
- guided: `ev-6ec9ec0fa9f1534a` — `docs/source-continuation.md:52–57`.

### projectB-Q39
- original: `ev-848dea5ff0c19302` — `README.md:70–76`.
- guided: `ev-848dea5ff0c19302` — `README.md:70–76`.

### projectB-Q40
- original: источников нет.
- guided: `ev-8c2a832e1b68357d` — `docs/modules/question-planning.md:23–29`.
