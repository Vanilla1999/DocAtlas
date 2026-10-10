# Patch validator: второй disjoint dictionary-exit slice

2026-10-06. Primary `/tmp/opencode/docatlas-stage3-integration-active`, baseline
`adc9abf8`. **Локально реализован; full advanced/legacy dictionary exit NOT DONE.**
Никаких network/commit/push. Первый SDK slice, его семь production files, tests и
report этим вторым заданием не редактировались. MCP parent integration files также
не редактировались; их параллельные изменения принадлежат интегратору.

## Exclusive scope и изменения

Production — только
`docmancer/docs/application/patch_constraint_validation_service.py`.
Новые файлы — только `tests/test_dictionary_exit_patch_validation.py`,
`tests/diagnostic_labels.dictionary_exit_patch_validation.json` и этот report.
Old tests/gold/freeze/thresholds не менялись.

- Удалены `POLICY_KEYWORDS`, `POLICY_DECISION_KEYWORDS`, `SAFE_UI_WIRING_PATTERNS`,
  layer/topic tables, policy decision regex, NL manual/normative classification,
  semantic lockfile-upgrade allowance и их consumers. Таблицы не перенесены.
- Explicit `architecture`/`behavior`/`semantic`/`manual_review`/`source_of_truth`
  types остаются `manual_review`; иные неподдержанные сравнения — `unknown`.
  Наличие service/provider path, API call, branch, version literal или opaque
  business decision не доказывает satisfaction и не вызывает guessed violation.
- `generated_file` остаётся явным техническим protection type. `forbidden_edit`
  сравнивает только explicit `files`: literal paths или supplied glob syntax.
  Lockfile/manifest/ordinary protected-path совпадение даёт `violated`, а NL
  upgrade intent не отменяет запрет. Source citation сама по себе не target.
- Некорректные строки не прячут корректные technical matches: valid protected
  lockfile + traversal/invalid row всё ещё дают violation и unresolved diagnostics.
  Malformed constraint rows представлены отдельными unknown, не тихо удалены.
- Changed/protected/source paths не допускают traversal, absolute/drive/UNC,
  control bytes или symlink aliases. Отсутствующий root/file не снимает lexical
  guard. Caller `a/`/`b/` components не отрезаются как Git aliases.
- Diff parser сохраняет deletion/rename sides и quoted literal paths, не читает
  hunk body как `+++` headers. Unsupported Git C escapes и malformed headers
  не дают положительного результата.
- Positive file-protection nonmatch разрешён **только как bounded supplied
  mechanical comparison**: explicit root, matching local source path, caller-supplied
  `source_refs[].kind=source`, **`file_bytes_sha256` raw-file digest**, exact
  `line_start`/`line_end` и matching `evidence_snippets[].text`.
  Это узкий opt-in byte-pin comparison, не новый source-authority protocol:
  обычные refs первого producer без такого pin остаются unresolved.
- Ambiguous `content_hash`/`sha256`, forged canonical hints, missing/stale source,
  wrong spans/snippets, mismatched packet project root и supplied nonempty
  `index_state` не дают satisfaction. Индекс/library/version/snapshot/freshness
  verifier в этом DTO отсутствует; их validation **не заявляется**.
  Unsupported provenance refs отвергаются до content read; внутренние CRLF/newline
  bytes literal span не нормализуются ради положительного совпадения.
- Source reads bounded и anchored через directory descriptors с `O_NOFOLLOW`
  на каждом open. TOCTOU replacement source на symlink не читается как source.
  На платформе без secure dir-fd/no-follow primitives positive read comparison
  fail-closed. Per-request byte cache не используется как shared freshness cache.
- Bounds: 1000 constraints, 4096 changed paths, 128 protected paths per constraint,
  4096 chars/path, 1M chars supplied material/diff, 1M bytes/source и 4M aggregate
  source-read bytes. Overflow — явный unknown/refusal, не prefix approval.
  Diagnostic text bounded; public signatures и status enums сохранены.

## SDK / hard API flags

Возвращается frozen subclass существующего `PatchConstraintValidationPacket`;
базовые fields/statuses/counts сохраняются. Additive fields проходят через обычный
`asdict` и `.to_dict`, включая реальный текущий MCP validator handler:

```
policy_coverage = unresolved
mutation_authorized = False
edit_ready = False
source_identity_validated = False
```

Даже all-satisfied literal comparisons не означают policy approval. Empty input
имеет low confidence и явное no-all-pass warning. Confidence ограничен low/medium,
не high proof при неизвестном source. `source_refs` сохраняются как supplied
metadata, а не автоматически удостоверенные citations. Technical `violated`
говорит о совпадении explicit supplied protection, не об authority его NL source.

## Проверки: штатный conftest, hashes, outbound-network guard

Команды: `PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest
-p no:cacheprovider -q ...`; `--noconftest` не применялся.

- **84 новых validator tests + 25 первого slice = 109 passed.** SDK и настоящий
  `handle_project_tool` без mocked validator: оба reviewer repro, strict mode,
  empty input, genuine pinned literal nonmatch и additive non-authorizing flags.
  Также path/symlink/readroot race, hashes/spans/staleness, opaque policy/API
  examples, generated/lockfile/manifest violations, malformed rows, diff grammar,
  input/source-read budgets и no invented upgrade permission.
- Old validator + MCP validator: **19 passed / 12 failed**:
  `tests/test_patch_constraint_validation_service.py`,
  `tests/test_mcp_patch_constraint_validation_tool.py`.
  Reds сохранены: semantic upgrade allowance, layer-based satisfaction,
  provider-policy guesses, safe-UI satisfaction и прежние summary counts/reasons.
- Scoped baseline diagnostic: те же два old modules, validator загружен read-only
  import loader из `git show adc9abf8:<validator path>` — **31 passed**.
  Остальная primary среда текущая; это не clean full-revision baseline checkout.
- Old technical/security: **45 passed / 1 failed**:
  `tests/docs/test_target_security.py`, `test_content_trust.py`,
  `test_reference_hash_domains.py`, `test_review_source_capabilities.py`,
  `test_finalized_mcp_output_integrity.py`, `test_mcp_boundary.py`.
  Единственный red — `test_patch_constraints_debug_compaction_preserves_contract_fields`:
  старый assertion требует `answer_available=True`, текущая parent MCP projection
  возвращает False. Ни assertion, ни parent implementation не менялись здесь.
  Один существующий Starlette deprecation warning. Это **не green security gate**.
- `git diff --check`: PASS. Tracked old tests/eval/workflows diff пуст.
  Full CI/MCP stdio/self-host/frozen quality rerun этим исполнителем не выполнялись.
- Final single combined run всех перечисленных new/old/technical modules:
  **173 passed / 13 failed**, тот же один warning. Все 13 reds — двенадцать old
  validator expectations и один parent MCP `answer_available` assertion выше.

Logs: `/tmp/opencode/patch-validation-final-new-tests.log`,
`patch-validation-final-technical-tests.log`, `patch-validation-final-old-tests.log`,
`patch-validation-baseline-old-tests.log`, `patch-validation-final-combined-tests.log`.
Suite lists/counts сохранены выше,
temporary logs не единственная точка handoff.

## Remaining integration / blockers

1. Parent owns `project_tools.py`, output projection и первую SDK семёрку.
   `answer_available`, `answer_supported`, packet availability и transport/status
   должны отражать unresolved policy и не выводить readiness из satisfied count,
   constraints presence, path literal, byte pin или `strict=True`.
   Текущий get-patch wrapper уже возвращает answer unavailable; старый positive
   assertion остаётся red. Validator SDK flags выше не заменяют parent review.
2. Full source/project/library/module/version/snapshot/freshness/provenance
   certification и explicit mutation target/action/lifecycle/consent authorization
   остаются отдельной границей. Local file-byte/span comparison не заменяет её.
   Ни один SDK/MCP результат этого validator не выдаёт edit grant.
3. Legacy patch-plan/typed-proof/premise/governance paths вне ownership и всё ещё
   OPEN. No full advanced cleanup/recall/security/release approval claim.
4. Primary меняется параллельно. После review нужен final combined snapshot run;
   старые красные проверки и quality thresholds сохраняются, не переклассифицируются.

## Scoped source pins на момент handoff

- Validator: `eb18ea507e74b931d6da46be0c303842147fcdb352db86dafb79da5ea48a4f78`
- New test: `7b2b14855d9188d747130017391dcb68277071fcae6c8dcc0180a330357b856d`
- New shard: `85f92949f99d682630aac8e826adb3d0b383e8bb624b60d2ddbdef473f554868`

Это scoped SHA-256 bytes snapshot, не frozen acceptance manifest.
