# Семантическое ревью двух V2 identities

Base: d2ed5c4c73dc3b7d56276fc37591cba8a4ae123c.
Это авторское техническое ревью, НЕ независимое одобрение.

## Git provenance

README frozen commit `be4e9c7e5aa2dfa3a99aabb06078ac7015f8a295`, blob
`1a1975b2ffaf587f3b752c1966acdb20e7a88468`.
SHA256 `4bc778b1dfaf72dcd1058427a8477841fea62e500b20913471ae05e74e9be2d9`
→ `82975e09e63a5897c0f0867fbf370af4038360e489a3baa71d6378b98f2498bb`.

Workflow frozen commit `2facdba3b84c1c5e4a396b4e0d06b2a5e32aacd4`, blob
`316a520a4df91ebb577da84c99d783c3583b035f`.
SHA256 `8900b87204a72862432f11f1f9433c6646d55663330c590044a947a5050c0f36`
→ `4478411a57217bd30378f232641481a5b8773dadda37f555204f724753c6fafa`.

## Все используемые факты

Ниже subject/value/condition/negation — одинаковы в frozen и active версиях.
Полные obligations, accepted_authorities/scopes, case questions, lookup IDs и
обязательные части каждого ответа записаны в `identity-proof.json`.
Проверены и неиспользуемые сейчас определения tool_prepare/tool_status:
они находятся в inventory, но не имеют прямых obligation_id references в cases.

| Obligation | Subject и значение | Условие / отрицание / scope |
|---|---|---|
| install | Установка DocAtlas через опубликованный install.sh | Latest published PyPI, не unreleased main; bash/curl инструкция неизменна |
| verify | `doc-atlas --version`, альтернативный doctor в wiki | Проверка установленной версии до применения нового unreleased workflow; соседнее предупреждение сохранено |
| purpose | Агенты не должны угадывать по stale/generic docs | Local-first; authority/scope/version binding; fail closed при недостающем mandatory evidence |
| product | Reviewable project docs, lockfiles, approved dependency docs → compact attributed evidence | Для coding agents; small MCP surface; repository/source identity не изменена |
| sync | `prepare_docs(action="sync_project_docs")` | После редактирования файлов/возвращённого next_action; явный sync доступен; не implicit mutation от context |
| stale | Удаление stale sections изменённых файлов | Changed files, не произвольное удаление индексированных данных |
| orphans | Pruning orphaned sources | Deleted/no longer discovered files; остальные этапы reconciliation и счётчики сохранены |
| catalog | Reviewable `docatlas.project-docs.yaml` | Nonstandard/many files; only validated exact documents/roots при наличии catalog; fallback при отсутствии |
| catalog_invalid | Invalid catalog fail closed | Retrieval/ingestion/sync блокированы **без pruning существующего index**; routing metadata не agent instructions |
| health | `docs_status` | Только explicit health/freshness/index/job; **не discovery step** |
| tool_prepare | Lifecycle sync/refresh/index/prefetch | Только bounded recommended/unbounded next_action либо explicit user request; network approval |
| tool_status | Health/freshness/index/background-job | Explicit only, не произвольное discovery |

Case→обязательные части:

- v2-natural-install-verify → install + verify;
- v2-natural-purpose-start → product + purpose;
- v2-natural-sync-renames → sync + stale + orphans;
- v2-natural-stale-health → health + sync + stale;
- v2-paraphrase-reconcile-files → sync + stale + orphans;
- v2-natural-catalog → catalog + catalog_invalid.

Остальные обязательные компоненты/соседние документы cases не менялись.
Catalog metadata authority=`source_of_truth`, scope=`project` для обоих файлов
сохранились, как и accepted metadata каждого obligation.

## Полный diff, не только substring

README: bold markup разделён по именам клиентов. Строка onboarding заменяет
устаревший `mode="project"` публичным question/scope и добавляет пояснение
project/all/module. Это реальное изменение соседней API-инструкции, но ни один
V2 obligation из этого файла не требует прежнего onboarding-вызова. Sync row
в той же таблице, lifecycle policy и все используемые условия не изменились.

Workflow: публичные примеры заменяют mode на scope=all; exact module фильтр
остаётся scope=module + module_path. Изменён текст о dependency metadata:
project-owned и external/version-bound docs остаются разделёнными. Добавлена
current-vs-history authority policy. Ни один V2 witness из этого документа не
задаёт выбор текущего/исторического источника или dependency/onboarding API;
catalog lifecycle exclusion для ordinary/history вопросов сохранён полностью.
В reason_code таблице готовый context-вызов изменён, но строки stale/unindexed
и sync action неизменны. В architecture-creation процедуре изменён retry syntax,
но original question unchanged и необходимость sync сохранены.

Установка, продуктовая цель, reconciliation, invalid-catalog отрицание и
explicit-health условия не приобрели новых исключений или другой области.
Таким образом **оба verdicts: IDENTITY_ONLY_SAFE относительно V2 used facts**.
Это НЕ объявление всех bytes/semantics всего документа неизменными.

## Проверка refresh

`verify_document_identity.py` проверяет исторические Git bytes, все witness
statement lines, полное cases equality, и точную обратимую подстановку лишь двух
document hashes и одного dependent protocol hash. Аналогичный исторический byte
proof: commit 18f53fe66e734142e929bfa2bd0e811eb8485cc0; workflow оттуда не переносился.
Новый product PR изменяет только два разрешённых lock-файла; тест/proof находится
в research evidence, чтобы не расширять разрешённый product diff.

Before: existing inventory test FAIL `active witness document revision mismatch`
на exact baseline/старом integration (опубликованное evidence).
After: все 47 существующих V2 protocol tests PASS; integration focused 110 PASS.
Полноценный V2 quality gate выполняется, но FAIL по semantic/attribution floors.
Обновление identities не ослабляет эти floors и не означает quality PASS.
