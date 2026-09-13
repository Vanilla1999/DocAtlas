# 40 новых вопросов: фактическая выдача и мои ответы

Проверка без модели. Ниже ответы, которые можно составить из полученных фрагментов; full означает достаточность evidence по ручной оценке, а не сертифицированный ответ DocAtlas. Режим guided добавляет один заранее написанный lookup на языке документации.

После первого прогона вопрос Q04 помог обнаружить и исправить потерю второго фрагмента при одном host lookup. Поэтому это открытый development/retest, не независимый holdout. Первичные ответы до этой правки сохранены в finish_new40_paired.json.

36 обычных вопросов: minimal/all — 10 full, 5 partial, 21 none; guided — 21 full, 6 partial, 9 none. Четыре отрицательных контроля — отдельно.

## Q01. Я впервые подключил MCP. Нужно ли каждый вопрос начинать с docs_status?

Без lookup: **full**. С lookup: **full**.

Нет. Первый вопрос — get_docs_context; docs_status нужен для возвращённого job_id или явного запроса статуса.

Пути в фактической выдаче: `docs/mcp-docs-server.md`, `README.md`, `docs/mcp-response-contract.md`.

## Q02. Which MCP tool should a coding agent call before modifying a documented module?

Без lookup: **none**. С lookup: **full**.

Перед первой правкой вызвать get_docs_context(project_path=..., question=...). В соседней цитате остался устаревший прямой вызов sync_project_docs: его нельзя выдавать за текущий публичный tool.

Пути в фактической выдаче: `docs/AGENT_DOCS_WORKFLOW.md`, `docs/project-docs-mcp-workflow.md`, `README.md`.

## Q03. В ответе есть цитаты, но answer_supported=false. Могу ли я объяснить найденное пользователю?

Без lookup: **none**. С lookup: **full**.

Да: false-флаги означают отсутствие серверной сертификации. Host может объяснить подтверждённые цитатами факты, назвать пробелы и не обещать полноту.

Пути в фактической выдаче: `docs/mcp-docs-server.md`, `docs/AGENT_DOCS_WORKFLOW.md`.

## Q04. How do I include module documentation when exploring the entire repository?

Без lookup: **none**. С lookup: **full**.

Использовать scope="all": найденная таблица явно включает repo-level и module docs.

Пути в фактической выдаче: `wiki/Architecture.md`, `docs/project-docs-mcp-workflow.md`.

## Q05. Мне нужны только общие документы репозитория, без module-документов. Как ограничить поиск?

Без lookup: **none**. С lookup: **none**.

Нужное ограничение области поиска в выданном контексте не найдено. Текст о доверии к Markdown не отвечает на вопрос о scope.

## Q06. Where do I declare which local documents are authoritative?

Без lookup: **none**. С lookup: **full**.

Авторитетные файлы объявляются в docatlas.project-docs.yaml; runtime-настройки поиска остаются в docatlas.yaml.

Пути в фактической выдаче: `wiki/Configuration.md`, `README.md`.

## Q07. Чем конфигурация поиска отличается от каталога авторитетных документов?

Без lookup: **partial**. С lookup: **full**.

docatlas.yaml задаёт index/retrieval defaults; docatlas.project-docs.yaml определяет авторитетные документы проекта.

Пути в фактической выдаче: `wiki/Configuration.md`, `docs/INDEX.md`.

## Q08. I committed a README change. How does the next documentation query become current?

Без lookup: **none**. С lookup: **none**.

Checklist релиза не объясняет, как обновить индекс после коммита README. Нужна конкретная lifecycle-инструкция.

## Q09. В рабочей директории есть мои незакоммиченные правки. Может ли MCP сам пересобрать индекс?

Без lookup: **none**. С lookup: **full**.

Для dirty или неопределённого состояния Git требуется подтверждение; prepare_docs повторно проверяет состояние и HEAD.

Пути в фактической выдаче: `docs/project-docs-mcp-workflow.md`, `docs/mcp-docs-server.md`.

## Q10. Can get_docs_context change the index by itself?

Без lookup: **full**. С lookup: **full**.

Нет: get_docs_context сам не согласует индекс. Он возвращает отдельное действие prepare_docs(action="sync_project_docs").

Пути в фактической выдаче: `README.md`, `docs/mcp-docs-server.md`, `docs/project-docs-mcp-workflow.md`.

## Q11. Подготовка вернула job_id. Что делать до повторного исходного вопроса?

Без lookup: **partial**. С lookup: **full**.

Опросить docs_status по возвращённому job_id; после успешной подготовки повторить исходный bounded get_docs_context.

Пути в фактической выдаче: `docs/mcp-response-contract.md`, `docs/project-docs-mcp-workflow.md`.

## Q12. Does requesting cancellation prove that a background job has stopped?

Без lookup: **none**. С lookup: **full**.

Нет. cancelling — подтверждение запроса, а не terminal status. Нужно прочитать фактический итог задания с ограниченным polling.

Пути в фактической выдаче: `docs/grounded-host-session.md`, `docs/source-continuation.md`.

## Q13. Почему estimated_tokens может отличаться от бюджета допуска docs_context?

Без lookup: **full**. С lookup: **full**.

estimated_tokens сохраняет ceil(UTF-8 JSON bytes/4). Admission отдельно берёт максимум этой оценки и o200k_base для полного JSON, в пределах 800.

Пути в фактической выдаче: `docs/retrieval-boundaries.md`, `CONTRIBUTING.md`, `wiki/Architecture.md`.

## Q14. Does the output budget include citation metadata as well as document text?

Без lookup: **none**. С lookup: **none**.

Ответ о включении метаданных в бюджет не попал в выдачу; пустой контекст не позволяет подтвердить этот контракт.

## Q15. Ссылка source_uri появилась в цитате. Нужно ли немедленно её открывать?

Без lookup: **partial**. С lookup: **partial**.

Найдено, что source_uri — необязательный локатор и читать можно точный выданный URI. Явное правило «не открывать автоматически» не попало в начальную цитату; это частичный ответ.

Пути в фактической выдаче: `docs/source-continuation.md`, `docs/grounded-host-session.md`.

## Q16. Can a continuation locator be used to read an unrelated file?

Без lookup: **none**. С lookup: **partial**.

Найдено требование использовать точный выданный URI. Полная привязка к исходному файлу отсутствует в начальной выдаче; проверка продолжения вынесена в отдельный опыт.

Пути в фактической выдаче: `docs/index-cleanup.md`, `docs/source-continuation.md`.

## Q17. Исходный файл изменился между поиском и дочитыванием. Что должен вернуть reader?

Без lookup: **none**. С lookup: **none**.

Получена общая инструкция синхронизации, но не правило reader при смене snapshot. Подменять этим конкретный результат reader нельзя.

## Q18. Can two different continuation locators return overlapping lines without detection?

Без lookup: **full**. С lookup: **full**.

Нет: host controller проверяет пересечения строк даже у разных локаторов; дополнительно действуют общие ограничения чтений.

Пути в фактической выдаче: `docs/grounded-host-session.md`, `docs/source-continuation.md`.

## Q19. Дочитывание не удалось, но часть ответа уже подтверждена. Нужно ли отказываться от всего ответа?

Без lookup: **none**. С lookup: **full**.

Нет. Сохранить подтверждённую часть, назвать неизвестное и предложить выполнимый следующий шаг; ошибка чтения не превращает частичный ответ в пустой отказ.

Пути в фактической выдаче: `docs/grounded-host-session.md`.

## Q20. What should the agent say when documentation covers only one part of my question?

Без lookup: **full**. С lookup: **full**.

Сообщить подтверждённую часть с источником, явно назвать неизвестную часть и следующий шаг либо нужный уточняющий вопрос.

Пути в фактической выдаче: `docs/grounded-host-session.md`, `docs/project-docs-mcp-workflow.md`, `docs/INDEX.md`.

## Q21. Можно ли выполнить shell-команду, которую документ предлагает агенту внутри цитаты?

Без lookup: **none**. С lookup: **full**.

Обычная документация — данные, а не разрешение выполнить команду. Даже точный официальный источник не переопределяет system/user/tool policy.

Пути в фактической выдаче: `docs/security/mcp-runtime-threat-model.md`.

## Q22. Does successful retrieval grant permission to edit files?

Без lookup: **none**. С lookup: **none**.

Фрагменты говорят, что runtime сам не пишет документы, но не дают достаточно прямого ответа о разрешении host на правку. Не считать отсутствие автоматической записи разрешением на edit.

## Q23. В двух проектах одинаковый README.md. Как не получить цитату из чужого проекта?

Без lookup: **none**. С lookup: **none**.

Контекст пуст: нужное правило project isolation в выдачу не дошло.

## Q24. Are evaluation reports eligible evidence for an ordinary operational question?

Без lookup: **full**. С lookup: **full**.

Для обычного operational-вопроса evaluation/planning/history исключены, если явно не запрошены. Сам этот вопрос явно упоминает eval; присутствие eval-цитаты здесь не доказывает обход source policy.

Пути в фактической выдаче: `wiki/Architecture.md`, `eval/project_context_quality/README.md`, `docs/adr/0003-context-first-project-reads.md`.

## Q25. Как ограничение per-source влияет на соседние фрагменты одного документа?

Без lookup: **none**. С lookup: **none**.

Найдено описание parent-child indexing и соседнего контекста, но отсутствуют условия per-source overflow. Этого недостаточно для ответа о квоте.

## Q26. Can an inactive indexing generation change the ranking of active documentation?

Без lookup: **full**. С lookup: **full**.

Нет. Active-generation FTS/BM25 статистика изолирована от inactive/candidate generations.

Пути в фактической выдаче: `docs/retrieval-boundaries.md`, `wiki/Architecture.md`.

## Q27. Зачем повторно проверять цитату после её сокращения?

Без lookup: **none**. С lookup: **partial**.

Выдача говорит о повторной квалификации видимого path/section/snippet после сокращения. Причина возможной потери конкретного факта раскрыта не полностью.

Пути в фактической выдаче: `docs/mcp-docs-server.md`.

## Q28. Why should a matching heading not be enough to support a requested fact?

Без lookup: **partial**. С lookup: **partial**.

Даже совпадающая цитата сама по себе не доказывает ответ на вопрос; semantic assessment принадлежит host. Отдельный механизм проверки heading-only совпадений здесь не показан.

Пути в фактической выдаче: `docs/grounded-host-session.md`.

## Q29. Какая часть работы доступна без сети и заранее загруженной языковой модели?

Без lookup: **partial**. С lookup: **partial**.

Подтверждён fail-closed offline test suite. Полный перечень runtime-возможностей без сети и model cache в этих фрагментах отсутствует.

Пути в фактической выдаче: `docs/testing.md`, `wiki/Configuration.md`, `docs/support-surface-policy.md`.

## Q30. What happens when a dependency version cannot be proven from the repository?

Без lookup: **full**. С lookup: **full**.

Без сильного repository evidence версия не становится exact: остаётся declared-only либо unbound. Эти состояния явно различаются.

Пути в фактической выдаче: `docs/DOCMANCER_PRODUCT_BRIEF.md`, `wiki/Architecture.md`.

## Q31. Можно ли использовать документацию latest как доказательство поведения установленной версии?

Без lookup: **none**. С lookup: **partial**.

Документ противопоставляет latest-only догадкам version-bound evidence. Для конкретной установленной версии нужна привязка; полный механизм отказа в этих цитатах не показан.

Пути в фактической выдаче: `README.md`, `docs/DOCMANCER_PRODUCT_BRIEF.md`.

## Q32. Can index cleanup run while another process is writing the index?

Без lookup: **full**. С lookup: **full**.

Нет: cleanup barrier отказывает, пока существует live writer lease.

Пути в фактической выдаче: `docs/index-cleanup.md`, `README.md`.

## Q33. Почему клиент может видеть только маркер structuredContent, без самой цитаты?

Без lookup: **none**. С lookup: **full**.

По умолчанию полный JSON находится в structuredContent, а text — маркер. Text-only клиенту нужен DOCATLAS_MCP_TEXT_FALLBACK=1; дублирования обоих каналов быть не должно.

Пути в фактической выдаче: `docs/mcp-docs-server.md`.

## Q34. How can I check that my installed MCP command matches the current package?

Без lookup: **full**. С lookup: **full**.

Проверить doc-atlas --version и документацию соответствующего релиза. main и установленный пакет могут различаться; installed-artifact smoke проверяет транспорт, не решения модели.

Пути в фактической выдаче: `docs/DOCMANCER_PRODUCT_BRIEF.md`, `docs/grounded-host-session.md`, `README.md`.

## Q35. Для чего генерировать agent-contract перед работой агента с репозиторием?

Без lookup: **none**. С lookup: **none**.

Контекст пуст: назначение agent-contract не донесено до финальной выдачи.

## Q36. Do successful provider-free tests prove that real agents spend fewer task tokens?

Без lookup: **none**. С lookup: **none**.

Выдан лишь CONTRIBUTING о запуске тестов. Он не доказывает экономию task tokens; отсутствие доказательства не заменяется зелёным CI.

## Q37. Где подтверждено, что DocAtlas всегда экономит ровно 50 процентов токенов?

Без lookup: **control**. С lookup: **control**.

Подтверждения гарантированных 50% нет; такое число нельзя утверждать.

## Q38. Which document guarantees that every query receives a complete correct answer?

Без lookup: **control**. С lookup: **control**.

Документа с гарантией полного правильного ответа на любой вопрос не получено. Не обещать универсальную гарантию.

## Q39. Какой пароль администратора установлен в моей частной production-среде?

Без lookup: **control**. С lookup: **control**.

Пароль частной среды неизвестен. Install-инструкция не содержит этой информации и не даёт права искать секреты.

## Q40. Where is mandatory ninety-day retention of every conversation specified?

Без lookup: **control**. С lookup: **control**.

Обязательное хранение всех разговоров 90 дней не подтверждено; контракт question planning этого не устанавливает.

## Отдельное дочитывание

Q16: одно чтение выбранного continuation добавило правило проверки repository identity, catalog entry и исходного snapshot; host смог завершить ответ. Q15: два чтения выбранного источника не нашли правило об отсутствии автоматического чтения — оно расположено выше стартовой цитаты. Известная часть сохранена, итог partial, stop_reason=read_budget_exhausted. Это два post-hoc примера с ручным выбором источника, не средний выигрыш reader и не модельный эксперимент.

Сырые публичные payloads, оценки и счётчики этапов: finish_new40.json. Ссылки source_uri в сохранённых payloads сессионные и уже не являются действующими разрешениями на чтение.
