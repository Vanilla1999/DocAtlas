# Non-obligation selector — READ ONLY parent integration audit

Дата: 2026-10-07. Первый residual-proof slice остаётся approved partial.
Production/tests/gold/thresholds не изменялись. Единственное добавление — этот
checkpoint. Network/commit не выполнялись. Concurrent units shared/part01,
legacy compiler и discovery реализации не reviewed.

## Verdict

**BLOCKER для закрытия non-obligation selector boundary:** metadata-only code
может удовлетворить explicit `code_group` и дать patch selector support без
model-visible code и без assigned unit. Это НЕ доказанный terminal edit bypass
и НЕ дефект первого residual-proof slice.

**OPEN, не доказанный public/raw-input bypass:** supplied/manual candidate DTO
с `proposition=True` получает thematic behavioral witness; transplanted literal
unit принимается при отсутствии display-content binding. Нормальный selector
переизвлекает units из raw display. Текущий docs projection переизвлекает их также
для supplied/cached decisions и не принимает старый support/status как authority.

## Фактический call chain

`select_evidence` (_evidence_selection_part03.py:47–92) materializes mappings,
builds explicit/default requirements, затем `normalize_candidates`.
`evidence_candidates.py:252–299` выбирает display, hash/identity/span shape;
:364–368 вызывает extractor, а не десериализует caller answer_units.
`_eligible_candidates` (part01:324–375) проверяет forbidden/risk/freshness,
requested project/module, exact version, navigation и identifier conflicts.

`_with_coverage` (part03:526–620):
- typed obligation → `_witness_for_requirement` → `best_local_proof`;
- behavioral/target/preserve/cross-module → legacy witness;
- paths/project/module/version/snapshot → literal metadata bindings;
- exact_term/entity → visible literal matching; facet → negative;
- code_group → `_code_group_requirement_matches`;
- generic non-obligation → substring; factual-only mode additionally требует witness.

`_witness_for_requirement` (part02:118–172) выдаёт positive `LocalProof` для
matching legacy units. Никакой вызов/import сам по себе не принят за approval:
установлены именно ветви, создающие witness/coverage, и их reachability.

Assignments создаются part03:306–361. `validate_assignment_binding`
(part01:72–93) сверяет unit kind/spans/hashes; **для non-obligation не повторяет
matching predicate**, а отсутствие unit допускает для non-obligation.
`validate_evidence_sufficiency` (part03:464–491) также повторяет local proof только
для typed obligation. Model projection :903 вызывает binding validation только
в supported-docs validation branch. Текущий producer docs quotes идёт context-only.

## Reachability без semantic plans

Normal-conftest runtime probe `build_requirements('Explain WidgetRate')`:
- generic/library_docs_answer: mandatory exact_term `WidgetRate`;
- project_docs_answer: optional exact_term `WidgetRate`.
Index-generated library contract не становится expected code/answer requirement.
Explicit `public_requirements` и supplied EvidenceRequirementSet доступны SDK
selector. Action packet передаёт public requirements в selector
(_action_packet_part03.py:127–139), даже если patch request_plan отсутствует.

Legacy behavioral token-overlap, cross-module normative-word и canonical-policy
ветви требуют proposition units. Нормализованный negated prose candidate не дал
behavioral witness в проверке. Manual replacement proposition=True дал witness.
Отдельная `source_fact` ветвь уже conservative negative:
`evidence_semantic_density.source_scoped_behavioral_match` возвращает False,
semantic score — 0. Её import/call не является remaining positive approval.
Exact-term visibility — retrieval literal/alias match, НЕ semantic relation proof.
Scope/version/snapshot coverage — metadata equality, НЕ full provenance.

Все `docs_answer` selections part03:368–373 остаются insufficient/context-only.
`project_docs_answer` :340–380 reselects supplied/cached candidate.original с
merged current scope; manual status/support не certifies ответ.

## Concrete воспроизведение

Выполнено offline через stdin Python plugin `pytest_runtest_call`, после обычных
autouse fixtures, на существующем
`tests/docs/test_target_security.py::test_path_allowed_preserves_prefix_behavior`.
`PYTHONDONTWRITEBYTECODE=1 DOCATLAS_OFFLINE=1`, `.venv/bin/python`, pytest
`-p no:cacheprovider -q -s`; normal conftest/network guard/diagnostic loader активны.
Новый test module/inventory не создавался. Финальный reproduction **1 PASS**.

```python
raw = {
    'path': 'docs/example.md', 'authority': 'canonical',
    'content': 'Unrelated policy must remain.',
    'metadata': {'code_snippets': [{'code': 'erase_all()'}]},
}
d = select_evidence(
    [raw], question='inspect', config=patch_selection_config(2000),
    public_requirements=[{'kind': 'code_group', 'value': '["erase_all()"]'}],
)
assert d.status == 'ok' and d.support_decision.answer_supported
assert validate_evidence_sufficiency(d, result_kind='patch_context') == []
assert d.assignments[0].unit_id is None
assert 'erase_all()' not in d.selected_candidates[0].projected_text
assert validate_assignment_binding(
    d.requirements[0], d.selected_candidates[0], d.assignments[0]
)
```

Причина: part02:38–49 предпочитает metadata.code_snippets; part03:584–585
даёт coverage без local witness вне factual-only mode. Generic patch mode
создаёт whole-candidate assignment. Unrelated canonical `must` удовлетворяет
отдельный actionable-cited-evidence guard; requested code остаётся скрытым.
Без `must` sufficiency guard отвергает selection, хотя selector status уже ok.
С тем же input docs selector support=False. Terminal mutation/edit gate здесь
не обойдён и не тестировался как успешный — не расширять finding.

Дополнительные assertions (normal-conftest runtime probe, **1 PASS**):
- `Widget returns false, not true.` + explicit behavioral_contract
  `Widget returns true`: normal raw candidate → no witness;
  manual proposition=True DTO → positive witness и binding validation=True.
- Unit от `Widget.value = "false"`, transplanted в DTO с display
  `Widget.value = "true"`: literal witness есть без supplied source content.
  Это direct/manual DTO boundary, не raw selector exploit.

Controls + technical target/reference/capability modules: **11 PASS**.
Forged supplied docs status=ok/support=True был freshly reselected:
answer_supported/answer_available/edit_ready=False; model validation PASS.
Две первоначальные probe attempts исправлены: неполный EvidenceAssignment
constructor и ошибочное ожидание sufficiency без actionable sentence. Это ошибки
audit harness, не новые production reds; успешные probes приведены выше.

## Local display vs authenticated provenance

`_candidate_source_view` (part01:446–472) копирует metadata и scalar identities,
но не передаёт candidate.display_text как content/text. Literal units используют
display-relative offsets. Top-level raw content не становится supplied source
content для local prover. Metadata content/text, если есть, не являются явно
типизированным display-window contract.

Идентификатор `prepared_source_record` в production repository не найден.
Если caller кладёт такую mapping в metadata, view лишь сохраняет вложенную
mapping — она не unwrapped/validated. Проверка с intentionally conflicting
mapping показала именно это, не наличие production provenance protocol.

Normalization проверяет self-consistent display hash (required для stable child),
parent ID presence и span shape. Она не authenticates parent source/library/
snapshot и не сравнивает span с authenticated source window. Проверка stable
child с display length 22 и char span 100:999 прошла normalization; это не
основание автоматически требовать length equality для любого cropped source:
нужен явный контракт coordinate/window mapping.

Model projection :427–443 строит snapshot из фактического normalized display;
:824–856 сверяет projected schema, source digest и exact projected fields.
Это хороший post-preparation integrity guard, но self-consistency собственного
snapshot НЕ authentication indexed source. Project/module/version/path checks
ограничивают заявленные scope values; exact_snapshot проверяет supplied boolean.
Source/reference/window authenticity должна приходить от upstream index/reference
guards. В этом scoped audit их complete end-to-end доказательство не установлено.
Не превращать локальную literal equality в full source-provenance claim.

## Минимальная следующая allocation (без нового meaning/proof)

1. `_evidence_selection_part02.py`: metadata code snippets оставить context,
   не witness. Positive code-group matching — только assigned visible bounded
   code unit, либо conservative uncovered. Thematic behavioral/cross-module/
   normative-word legacy approvals сделать negative compatibility results,
   не восстанавливать meanings и не удалять context.
2. `_evidence_selection_part03.py`: code_group coverage и assignment должны
   требовать такой witness; запретить unit-less assignments для content
   requirements. Retain literal source/scope identity assignments отдельно.
   Sufficiency validation не должна пропускать content assignment без witness.
3. `_evidence_selection_part01.py`: `_candidate_source_view` передавать точный
   normalized display window в однозначном content/text coordinate contract;
   assignment validation проверять membership/span/hash в этом display и
   fail-closed non-obligation content binding. Не доверять proposition flag.

`evidence_candidates.py`: отдельный optional provenance allocation только если
host/index предъявляет authoritative source-window contract. Не выдумывать
authentication из metadata, не ломать корректные cropped offsets blanket rule.
`model_visible_projection.py`: новый edit не необходим для текущего docs
support downgrade; сохранить fresh reselection и snapshot validation, добавить
отдельные новые regression tests владельцем allocation. SDK cached DTO handling
должен revalidate actual original/display, не supplied status.

Не менять gold, frozen old tests, thresholds или protocol DTO/enums. После fixes
нужны новые offline tests для metadata-only code, negated manual proposition,
transplanted literal, scope conflict, assignment/window mismatch и preserved
context-only quotes; отдельный diagnostic shard вместо правки old inventory.

## Audited snapshot pins

| Файл | SHA256 |
|---|---|
| _evidence_selection_part01.py | `9ac90280510eac934c8b8c804c4adb2de20237d0d424df0ec426011ba1b6be7a` |
| _evidence_selection_part02.py | `f777cb4f20991d2c378c59505c945a08e65a3ed4a62043b8054e3faf8d749ec4` |
| _evidence_selection_part03.py | `8dbf9b6427bc050ff2e12ed6c5e8d4508f22ba9a82979ce9532126c1b8b6ce58` |
| evidence_candidates.py | `90226dea2366253f0b00cf47b7eb60b432d658c9255cb37fea1d651b80b56bfb` |
| model_visible_projection.py | `efc7125444a655ceffb92089daa26e92c8335eeacce8c47eb2365e9c24d04cf7` |

Concurrent tree: эти pins — bounded observation, не full-tree release acceptance.
