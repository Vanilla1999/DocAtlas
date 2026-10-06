# Explicit SDK / advanced patch: bounded dictionary exit

2026-10-06. Primary `/tmp/opencode/docatlas-stage3-integration-active`,
HEAD/baseline `adc9abf8cfc939ef1e44e8895c00b448b77033b3`.
**Реализован локальный bounded slice; full dictionary exit NOT DONE.**
Commit/push/network не выполнялись. Параллельные corpus/audit изменения не принадлежат
этому исполнителю и не редактировались им.

## Exclusive изменения

Только семь production files:

- `_patch_constraints_service_shared.py`: удалены `PHRASE_ALIASES`, generic-call/
  asset-topic словари, policy keyword/heading/owner-suffix regex; импорт нормативного
  NL classifier больше не нужен. Manifest/lockfile, generated-file и artifact/source
  boundary mappings оставлены как технические, не как topic dictionaries.
- `_patch_constraints_service_part01.py`: changed-file stems больше не переписываются
  в guessed phrases; filename/topic authority, example-heading и normative-policy
  классификация удалены. Compatibility helpers не выводят authority из прозы.
  Packet предупреждает о unresolved policy coverage, не разрешает mutation.
- `_patch_constraints_service_part02.py`: prose architecture/generated-policy
  extraction удалена; нет guessed owners/delegates/API names. Task terms — bounded
  explicit quotes/backticks и code-shaped literals, без aliases/stopwords/phrase
  compaction. Symbol должен сам совпадать с requested spelling на границе identifier;
  соседний вызов и comment-only строка не подменяют requested symbol. Generated
  registry допускается по explicit changed path, не asset-topic вопросу.
  Literal candidate сохраняет line reference. Symbol evidence не становится
  source-of-truth rule. Dependency intent определяется explicit manifest/lockfile
  changed path; exact observed pinned versions сохранены.
- `_patch_constraints_service_part03.py`: owner/delegate policy parser и topical
  sorting/dependency boosts удалены; next action — `manual_review_required`, не
  `edit_with_constraints`. Literal/structural ranking и budget clamp сохранены.
- `_patch_review_service_shared.py`: удалены `LOW_VALUE_SYMBOLS`,
  `TASK_TOKEN_STOPWORDS`.
- `_patch_review_service_part01.py`: coverage categories зависят от explicit type,
  не instruction/reason topic words. Coverage/advisory явно имеют
  `policy_coverage=unresolved`, `mutation_authorized=False`. Advisory требует manual
  review даже при empty/all-satisfied/forged-resolved supplied coverage.
- `_patch_review_service_part02.py`: удалены inline API aliases, product-specific
  exclusions, policy boosts и NL triage dictionaries. Остаются literal lexical
  ranking, structural import/export/part syntax и explicit confidence/status/type.
  Unknown не классифицируется автоматически как low-risk/pass.

Все paths выше находятся в `docmancer/docs/application/`.
Facades `patch_constraints_service.py`, `patch_review_service.py` **не изменены**:
import adaptations не понадобились. Удалённые словари не перенесены в другой модуль,
prompt или config. Explicit mutation target/action, source scope/version/snapshot,
freshness/hash/span/provenance, consent/lifecycle и readiness consumers вне owned
files не менялись. Green ниже — bounded проверка, не доказательство всех guards.

## Новые tests и штатный conftest

Только `tests/test_dictionary_exit_patch_literals.py` и
`tests/diagnostic_labels.dictionary_exit_patch_literals.json`.
Hash связан с collected base node IDs; никаких old labels/assertions/gold/freeze/
threshold изменений. Штатный conftest и outbound-network guard включены.

**25 passed**: EN/RU no guessed APIs, exact explicit APIs включая прежние low-value
symbols, same-line call mismatch, substring/case mismatch, comment-only строки,
no prose authority, empty relevance no universal match, generated/lockfile/version
guards, budget truncation, symlink/root escape, type-only categories, unknown manual
handling и empty/forged coverage no approval.

Команды запускались с `PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1`,
`.venv/bin/python -m pytest -p no:cacheprovider -q`.

## Неизменённые old suites: честные результаты

- Security: **46 passed** — `tests/docs/test_target_security.py`,
  `test_content_trust.py`, `test_reference_hash_domains.py`,
  `test_review_source_capabilities.py`, `test_finalized_mcp_output_integrity.py`,
  `test_mcp_boundary.py`. Final combined security + new: **71 passed**, один
  существующий Starlette deprecation warning.
- Mixed: **136 passed / 62 failed** — `tests/test_patch_constraints_service.py`,
  `test_patch_constraint_symbol_grounding.py`, `test_patch_constraint_validation_service.py`,
  `test_patch_review_command.py`, `test_patch_review_command_part02.py`,
  `test_patch_review_command_part03.py`, `test_patch_review_command_part04.py`,
  `test_patch_constraints_workflow.py`, `test_mcp_patch_constraints_tool.py`,
  `test_mcp_patch_constraint_validation_tool.py`, плюс
  `tests/docs/test_patch_request_plan.py`, `test_patch_requirements.py`.
- Differential diagnostic: те же mixed suites с **семью owned modules**,
  загруженными read-only import loader из `git show adc9abf8:<path>`:
  **170 passed / 28 failed**. Остальная primary среда остаётся текущей; это не clean
  full-baseline checkout. 28 прежних reds — request-plan/requirements ожидания NL
  mutation inference; дополнительные 34 reds связаны с removed policy/aliases,
  symbol inference, summary/triage/coverage и advisory presentation. Не PASS.
- Additional readiness/mixed: **29 passed / 9 failed** —
  `tests/test_source_search_edit_readiness.py`,
  `tests/docs/test_storage_mutation_lock.py`, `test_review_assignment_identity.py`.
  Reds: три recovery/story ожидания и шесть positive requirement/assignment ожиданий.
  Для этих девяти baseline differential отдельно не запускался.
- `git diff --check`: PASS. MCP smoke/full CI/self-host/frozen quality gate не
  запускались этим исполнителем; прежние quality reds не заменены green claim.

Локальные logs: `/tmp/opencode/sdk-patch-final-security-tests.log`,
`sdk-patch-final-mixed-tests.log`, `sdk-patch-baseline-mixed-tests.log`,
`sdk-patch-readiness-tests.log`. Эти временные logs не единственная точка handoff:
suite lists и counts сохранены здесь.

## Remaining integration boundaries / blockers

1. **`patch_constraint_validation_service.py` вне ownership**: live
   `POLICY_KEYWORDS`, `POLICY_DECISION_KEYWORDS`, `SAFE_UI_WIRING_PATTERNS`, layer/topic
   matching, normative/manual/lockfile-intent parsing всё ещё есть. Raw supplied
   constraints могут получать `satisfied` по таким heuristics. Owned review больше
   не превращает это в policy approval, но standalone validator требует отдельного
   dictionary-exit slice. No full advanced-path cleanup claim.
2. **`docmancer/docs/interfaces/mcp/project_tools.py`**: patch tool выставляет
   `answer_available=bool(constraints)`/`status=success`. Это наличие advisory packet,
   не policy completeness/authorization. Compactor сохраняет warnings/next_actions;
   downstream consumers обязаны не трактовать status/count как разрешение edit.
   Owned packet не добавляет `edit_ready=True`.
3. **`source_map.py` / `code_graph.py`** вызываются для source/repo-map evidence;
   constraints здесь остаются advisory. Source-map audit меняется другим агентом
   параллельно; этот исполнитель не объявляет его semantic debt закрытым.
4. Legacy `_patch_plan_context_part01.py`/`part02.py`, supplied-obligation proof и
   question/premise/governance parsers вне scope. Explicit SDK request readiness,
   version/snapshot/hash/span/source authorization остаётся отдельной границей;
   quoted code occurrence и constraint count её не заменяют.
5. Primary одновременно меняется другими исполнителями. Integrator должен
   перепроверить combined source snapshot, новые shards и неизменённые old security/
   mixed suites после объединения, сохранив красные quality results.
