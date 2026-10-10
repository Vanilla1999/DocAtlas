# MCP delivery: проверенное состояние

База PR #211: `2d060bf0`. Интеграционный runtime snapshot: `5de649fa`.
Это промежуточный отчёт, **не merge/release acceptance**.

**SUPERSEDED:** финальное safe-closed состояние и installed результаты см.
`FINAL_REPORT_RU.md`. Pre-hardening положительные записи ниже не являются
acceptance финального runtime: в нём preparation намеренно заблокирован.

## Что реализовано

- Coding workflow явно использует v4; omitted/null сохраняет docs mode.
- Native consumers сохраняют полные источники без representation caps.
- Projection и agent проходят прежний line-budget <=1000 без повышения порога.
- Явный confirmed member-only lexical upsert с generation/ownership checks,
  SQL rollback и без orphan deletion/vectors/extraction publication.
- OpenCode V2 installer сохраняет имя, disabled state и посторонние настройки;
  конфликт/неоднозначность/небезопасный JSONC rewrite отклоняются.
- Sync validation не создаёт project facade до проверки member bindings.
- Активные проверки мигрированы точечно; historical gold/thresholds/reports
  и evaluation suites не менялись и не запускались.

## Проверки

- 984 выбранных offline product/security tests: PASS, normal conftest.
  Это не полный CI и не исторический acceptance suite.
- Scope, syntax, whitespace и общий line-budget: PASS.
- D1 catalog bytes неизменны: exact 10 documents, `code_files=()`.
- R независимо закрыл nested-`servers` installer defect R4 и narrowly
  request-triggered constructor-isolation defect. Остальные findings открыты
  в `REVIEW_R_INITIAL.md` до независимого re-review.

## Реальный установленный wheel / stdio

C использовал изолированный wheel, реальный subprocess/MCP/retrieval,
без repository PYTHONPATH и без mock retrieval. В обоих transport modes:

- Missing grant: отказ, bytes/rows fixture DB не изменены.
- Explicit indexing: 2 members, 2 derived writes.
- Unchanged repeat: 0 derived writes, 2 unchanged members.
- Stale grant: отказ, member rows не изменены.
- Invalid manifest: terminal failure, zero pages, без retry.
- Indexed retrieval: **0 sources / 0 bytes**; default docs недостаточен,
  complete/partial/project/all patch queries возвращают failure/unavailable.
- Из 50 113-byte fixture >32 KB evidence не доставлены.
- Module/version mismatch fail closed; positive binding coverage не доказана.
- Full installed smoke: **FAIL**, не PASS.

Найден конкретный разрыв: project retrieval фильтрует `project_identity`,
а исходная member-транзакция его не сохраняет. Исправление маршрутизировано A;
filter нельзя ослаблять или расширять corpus ради smoke.

Лог C: `/tmp/opencode/mcp-delivery-c-validation/full-smoke-961b3e72.log`.

## Открытые границы

- Filesystem/journal binding, input hardlinks/read budgets/platform guard:
  A hardening + R re-review.
- Host delivery ambiguity, syntactic witness binding, line span integrity,
  explicit recovery bindings: B fixes + R re-review.
- Cold DB initialization/migration не реализованы; lane требует existing
  project-local `.docatlas/docatlas.db`.
- Windows positive preparation не установлена.
- Остались активные старые v3 packet fixtures в docs unit tests; их статический
  inventory обнаруживает removed max_tokens calls. Historical criteria не
  переопределяются под новый результат.
- Новый remote CI SHA ещё не принят; зелёный CI не заявляется.
- Live installation/config, индекс пользователя, main, version number,
  публикация и merge не менялись. Primary worktree сохраняет прежний HEAD
  `b89fa3cc` и прежний untracked `v2plan/artifacts/`.

Ownership и запреты: `CONTRACT.md`; воспроизводимая проверка изменений:
`VERIFY_SCOPE.py`. После следующих commits этот snapshot superseded;
новые результаты должны быть проверены и записаны отдельно.
