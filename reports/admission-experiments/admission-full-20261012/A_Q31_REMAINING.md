# A — оставшийся Q31: bounded read-only final trace

## Итог для финального отчёта

**Q31 остаётся delivery FAIL при B1 не из-за отсутствия исходного факта в найденных candidates.** Факт `[3980,4070)` полностью покрыт двумя соседними acquired windows `[3770,4000)` и `[4000,4198)`, но оба имеют null partial admission; затем project context пуст и delivery заблокирован до projection. **Конкретный source-level blocker — сохранённая whole-term unresolved-name/owner boundary:** query mention `HumanEval` не принимается из единственного source spelling `HumanEval/LeetCode`. Это статическая реконструкция достаточного условия отказа, **не записанный внутренний branch receipt**.

Не ослаблять guard, не переписывать вопрос/источник и не пытаться получить 40/40 новым вызовом. B1 снимает topical witness, но **не все lexical identity/owner/numeric boundaries**. Поэтому 39/40 следует описывать как результат constrained candidate delivery, а не полного удаления literal admission и не качества 40 сгенерированных ответов.

## 1. Evidence identity и разрешённая работа

Всё ниже — text/JSON/hash inspection без product imports/runtime, unit/private-helper execution, новых model calls, patches продукта, CI или commits. Создан только этот отчёт и обновлён `A_PIPELINE.md`.

- Repo base HEAD: `4849b8f796d9e3e25e2c49e58562ec6859978411`.
- Product bytes всех трёх A-файлов повторно хешированы и **не изменились** относительно G-reviewed patch:
  - `original_body_discovery.py`: `b80209618be43b78bd501abde5e77a04f09e5a26cb4b0e52840ebec8f14ffc14`;
  - `ordinary_body_context.py`: `b069de048f7ae4d3e64b87710a0c709671f0e3e47f4d5e3da12d10dd37c5eedb`;
  - `literal_context_admission.py`: `324d4e9994d539f5938ac614543f5ebdfbdd0ce6a5b95649a3fdc94bc75e3cc9`.
- Current worktree также содержит изменение `eval/main_flow_comparison/run_extra40.py` другого владельца; оно не тронуто A.
- Raw `/tmp/opencode/docatlas-review-evidence/admission-full-20261012/B1_COMBINED40.json`, SHA-256 **`a77692384614c263d8636c96fc1531fa74e9009316df58a0903c0d30f7b3793d`**.
- Самостоятельно проверено: `.results[id=31]` byte-semantic JSON content полностью равен Q31 record в `live-B1/extra40-results.json`; в `live-B1-resume/extra40-results.json` Q31 отсутствует. Таким образом это сохранённая исходная попытка, не выбранный удачный retry.
- Общий combined40 — assembly двух реальных preparations/generations; не один непрерывный run. Независимая оценка остальных rows и accounting — `G_RUNTIME_REVIEW.md:35–46`, `G_RUNTIME_DATA_AUDIT.json`, не новая оценка A.

Все raw line references ниже — к указанному `B1_COMBINED40.json`; code paths — относительно repo.

## 2. Что непосредственно наблюдается

### Исходный вопрос и публичный отказ

`B1_COMBINED40.json:274255–274290`:

> Можно ли назвать reward hacking любое прохождение видимых задач HumanEval с провалом скрытых?

`lookup_variant=no_lookup`, `lookup_queries=[]`; frozen required span `[3980,4070)`:

> прохождение видимых тестов при провале скрытых само по себе не объявляется reward hacking.

Независимый первоисточник: `eval/main_flow_comparison/questions_extra40.json:195–202` и `corpus.md:69`. Corpus факт имеет SHA-256 `f4352a297bc6f657c5ed7ec3ab94e36ff681949a1a424d2cb0a50eea51cd841f`. Публично `status=insufficient_evidence`, sources отсутствуют, `context_available=false`, `answer_supported=false`, `answer_available=false`, `edit_ready=false`, delivery false/required_evidence_missing. `validation_snapshot={}`. Saved `elapsed_ms=92.47` — не новый замер A.

### Найденные окна и qualifier

Same-call `payload.diagnostics.delivery_observations.returns[0]` — member read (`:277183`), реально **9 windows**, omitted=0, status success/project_docs_ready. Первые два:

| Window / stable ID | Original span | SHA-256 independently reproduced from corpus | Qualification |
|---|---|---|---|
| `child-234f931d1b1972810018b08256260df55c516977` | `[3770,4000)` | `608b602bf8c9c9e2ccea0d85ef133d43188d9efd07691f82da05896c0ea59cb1` | matches `прохождение`, `видимых`, `humaneval`, 3/13=.2308; null admission |
| `child-e6881165adaf9f4dce8e9ce62cb37adee2be00ba` | `[4000,4198)` | `8784daeb3c3e16f838fc5ebc059080d858b525102a24d787ac798012d3ff6adf` | matches `reward`, `hacking`, `скрытых`, 3/13=.2308; null admission |

Member raw spans: `:277219`, `:277243`; qualification rows `[0]/[9]` и `[1]/[10]`, primary details `:274493–274568`, `:274640–274713`. Девять source window hashes самостоятельно совпали с Unicode corpus slices; repeated qualification entries — повторные наблюдения **одной call**, не отдельные executions.

Первое окно заканчивается `...Перенос на HumanEval/LeetCode (§5) оценивали отдельным монитором; прохождение видимых `; второе начинается `тестов при провале скрытых само по себе не объявляется reward hacking.`. Факт проходит через границу 4000: **нет одного окна с целым фактом**, но union двух acquired windows полностью его содержит. Нельзя назвать это полной retrieval-missing причиной; совместная source delivery могла бы дать полный факт, если бы окна прошли admission. Это отличается от Q46/Q16, где целый факт был в одном окне.

Оба окна: README/project/current/active/stale=false, version `""`, snapshot `gen-d9b377a9f1a344f8ae92120d6a03e051`, project `local:c98693d7525f05e658f12eb812f6041e67c4908715429066ff597a81c51d5255`, frozen document hash `31da2449b89b3edc72f6f463a84144d256105a77f99bfe5c7bdeab9cdd3c1d00`; root_catalog_complete=true.

### Важное различие constraints

- Raw root reference: **`HumanEval`, unresolved, nonexplicit**, original question span `[64,73)` (`:274505–274517`, `:274650–274662`).
- Canonical `observed_qualification.exact_terms=[]`, `missing_exact_terms=[]`, `bound_subjects=[]` (`:274540–274558`, `:274685–274703`). Поэтому **наблюдаемого canonical hard-exact denial нет**.
- Acquisition `candidate_lexical_match.exact_terms` содержит `можно/humaneval` и missing entries, но это backend lexical metadata, **не canonical hard-exact**. Нельзя объявить слово `Можно` обязательной exact identity.
- Project support requirements содержит optional (`mandatory=false`) `query_symbol:0:humaneval`, kind exact_term. Это downstream compatibility requirement, не основание превращать canonical unresolved mention в mandatory hard-exact.
- В исходном вопросе нет numeric term. Same-block numeric guard здесь не объясняет отказ.

### Публичная граница потери

Project context return (`:277449`, `context_windows :277477`) имеет count=0, project_docs.result_windows count=0, reason no_reliable_context, delivery false. Unified return (`:277611`, `context_windows :277644`) count=0 и required_evidence_missing. `stage_status.delivery=blocked_before_projection` (`:274297–274304`), `pre_projection_qualified_ids=[]`. Ни private discovery ledger, ни конкретный None-return guard в этом raw не показаны.

## 3. Статическая реконструкция конкретного blocker

1. `domain/query_reference_binding.py:61–93` оставляет bare technical spelling unresolved, а не semantic subject/explicit identity. Это соответствует наблюдаемому root mention HumanEval.
2. `domain/ordinary_body_context.py:25` `_TERM = re.compile(r"[\w.:/\\+-]+")`; `:46–53` сохраняет целый term, обрезая только terminal dot/colon. **Slash не разделяет term**. Единственное появление строки HumanEval во всём frozen corpus — **`HumanEval/LeetCode`**, `[3925,3943)`, `corpus.md:69`. Стандартный text поиск независимо подтвердил count=1; production tokenizer/AST не исполнялся.
3. Shared guard `_policy_valid_body_blocks` (`ordinary_body_context.py:212–231`) сначала требует native receipt и owner integrity, затем ищет каждый unresolved mention в complete literal `subject_terms` проверенного owner scope (либо body без owner). Он допускает **равенство whole term** или **first underscore namespace segment**, но не slash prefix (`:223–231`). Следовательно `humaneval/leetcode != humaneval`, а `_`-prefix route отсутствует. Поскольку bare HumanEval нет вообще в документе, даже более широкий корректный owner scope не даёт требуемый term. Этот guard достаточен для отказа всех указанных acquired candidates, независимо от того, имеют ли они общий owner или owner=None.
4. Source preparation строит owner из immutable текущего документа (`application/source_reference_evidence.py:109–125,182–200`); owner integrity rechecked в `domain/source_subject_binding.py:23–53`. Здесь **не доказан malformed/cross-owner source rejection**: обнаруженная граница — допустимая форма unresolved-name присутствия в owner/body, а не чужой owner. Нельзя путать эти два свойства.
5. Обычный и B1 lanes используют **один** shared guard (`ordinary_body_context.py:253–259,272–287`). B1 отменяет topical phrase/technical second-term requirement **после** eligibility; он не может bypass unresolved-name check. Admission caller допускает fallback лишь после insufficient_visible_match (`literal_context_admission.py:288–300`), затем raw-window/no missing-exact (`:368–379`). Для Q31 типический отказ происходит на shared unresolved-name boundary до numeric/body witness, если более ранние source/receipt проверки прошли.
6. No admitted/qualified windows → `domain/project_doc_ranking.py:205–225` исключает их; public invocation `application/_project_context_service_part01.py:156–175`. Далее пустой packet и no_reliable_context (`_project_context_service_shared.py:489–492`), delivery checks (`_project_context_service_part01.py:879–909`), public veto (`interfaces/mcp/context_tools.py:358–384`, `model_visible_projection.py:466–494`) объясняют наблюдаемую до-projection границу. Compaction/closure после этого не исполняется для восстановления пакета.

**Граница доказательства:** null admission и empty downstream packet — runtime OBSERVED. Whole-term slash-vs-bare rejection — SOURCE-RECONSTRUCTED sufficient blocker. Private receipt наличия/возврат exact internal branch не зарегистрированы; дополнительные более ранние причины не исключены. Не утверждаем наблюдённую трассу конкретного `return` и не выдаём гипотетическую нормализацию slash за проверенный fix.

## 4. Конкретное ограничение и остановка

Для финального отчёта:

> B1 доставил обязательные факты 39 из 40 unchanged direct questions; Q31 остался пустым. Его полный факт был acquired совместно в двух соседних окнах, но retained unresolved-name constraint не принимает `HumanEval` из source spelling `HumanEval/LeetCode`. Внутренний отказ реконструирован статически, а raw подтверждает null admission и veto до projection. B1 сохраняет эту identity/owner lexical boundary; достижения 40/40 или исправления Q31 не заявляем.

Это не numeric restriction и не наблюдаемое hard-exact miss. Это **консервативная unresolved-owner whole-token constraint**, сохранённая по assignment. Хотя source корректно упоминает HumanEval в естественном сравнительном slash notation, текущий guard не интерпретирует такие отношения. Ослабление composed-token handling — отдельный contract/security/relevance review; оно не разрешено и здесь не предлагается к немедленному patch.

Никаких новых questions/lookups, модельных/продуктовых вызовов, patches guards или retries ради 40/40. Исследование завершено на сохранённом доказательстве; runtime outcome/источник independently reviewed G, а этот отчёт уточняет только оставшийся blocker.
