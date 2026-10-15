# Slice 26: P1.4 через текущий public retrieval с независимыми фактами

Исходные `paraphrase_protocol.json` и исторический report не изменяются.
Root отдельно прочитал frozen corpus: **14 вопросов, 10 required discoveries,
5 полных обязательных фактов, 2 wrong-source negatives**, семь семей по два
случая. Questions, paths, candidate texts и labels сохранены буквально.
Миграция контракта вынесена в `paraphrase_contract_migration.json`.

Каждый случай получает собственный конечный docs catalog и реальные confirmed
member preparation / public get_docs_context через существующий fixture runtime.
Запрашивается исходный вопрос, scope project, без lookups. Oracle отдельно
проверяет frozen source bytes, coordinates, candidate hash domain, project/scope,
same-call projected-source binding и неизменность store/catalog/documents после
чтения. Подготовка отделена от проверяемого read-only вызова.

Прежние пять support-positive обязаны показать **полный прежний факт** в одном
видимом источнике. Отсутствие answer/edit permission по нынешнему retrieval-only
контракту не превращает пустой результат в PASS. Wrong-source negatives требуют
отсутствия чужого visible source. Typo cases сохраняют прежние необязательные
метрики; новый числовой output ceiling не вводится.

Новый versioned report записывается до quality exit и сохраняет все14rows,
включая execution/setup errors. Каждые row, assessment, summary и verdict
пересчитываются по frozen input. Same-process module inventory, source SHA256 и
Git checkout identity не заменяются историческим model report.
Пять compact oracle controls явно имеют тип oracle_unit_control; runtime scorer
не принимает их за реальные executions. Проверяются потеря source/fact,
подмена path/project/coordinates/hash, lookup credit, storage mutation,
answer/edit authority и resealed source hash.

Root independent review: APPROVE после полного чтения5files, frozen corpus и
actual capture helper. Workflow отдельно reviewed docs_quality_impl: APPROVE.
Runtime и self-control steps разделены; честный quality FAIL не блокирует проверку
integrity и always upload JSON. Permissions/dependencies/triggers/thresholds
не ослаблены, offline flag явный. P1 closure не пересаживается скрыто на новый
report protocol; его отдельная интеграция ещё открыта.

Local AST/runtime **NOT RUN** после exec transport outage. Новый P1.4 PASS
не заявляется до ordinary CI. Это fixture-public-API evidence; реальные
Claude Code/Codex/OpenCode sessions и автономное поведение модели не проверены.
