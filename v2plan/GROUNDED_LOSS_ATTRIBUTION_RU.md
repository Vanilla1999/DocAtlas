# Где теряются факты: discovery или admission

**Уточнение 2026-10-03:** [independent layer review](ADMISSION_LAYERS_REVIEW_RU.md)
обнаружил case-handling bug research adapter. Списки missing literal/subject ниже
содержат ошибочные diagnoses. Stage attribution относится к историческому adapter;
нельзя переносить его причины на native predicate. Новый review разделяет слои.

2026-10-03. **Исследование выполнено без изменения runtime и budgets.**

## Решение

- 01–04 сохранить как изолированные API; повторные controls Green.
- Старый Gate A и нынешнюю replacement-связку не развивать как production design.
- Основной измеренный блокер — **admission над уже найденными окнами**, а не
  отсутствие фактов в FTS. Отдельный discovery blocker — per-source hydration cap.
- Следующее изменение должно разделить source-bound subject, literal requirement,
  applicability и topic locality. Нельзя лечить всё снятием topic check.
- Не повышать final budget дальше, не менять production route и не выдавать
  semantic completeness из структурной целостности.

## Метод: только необходимое, воспроизводимо

Вход — сохранённые 560 rows прогона `grounded-budget-20261003-06`, 80 frozen cases,
88 required claim annotations. Новая сетка budgets и повторная native retrieval
не запускались. Script: `v2plan/grounded_loss_audit.py`.

Проверены frozen corpus hashes штатным `load_protocol`/`documents_for`, exact
source contents в archived generation. Archived DB открываются **read-only**.
Заново построен inventory из **сохранённых hits**, source context того же request/
generation; replay reasons и proposal IDs совпали с записанными decisions всех
шести strict cells. Diagnostic FTS inspection читает полный archived MATCH order,
не передаёт дополнительные hits selector и не обходит source policy: проверено,
что весь source pool проходит existing metadata eligibility.

Для каждого claim отмечается наличие **полного literal annotated witness set**:
в source, retrieved passages, proposed windows, admitted windows, final DTO.
Multipart witness требует всех parts с правильными canonical paths. Отдельно
сохранены missing literals/subjects и native read result на witness-bearing windows.

Baseline/final `supported` берётся из неизменённого `assess_context`; attribution
строится post-selection по annotation spans. Gold не участвует в retrieval,
window construction, admission или ordering. Literal absence не доказывает
semantic absence; source/unreviewed claims не объявлены production дефектами.

## Разложение потерь baseline

Baseline evaluator подтвердил 49 required claims. Ниже — только ранее supported
claims, ставшие not-supported в исследовательском cell.

| Policy / budget | Потерь | Discovery pool | Admission | Packing/final |
|---|---:|---:|---:|---:|
| Passage / 800 | 36 | 4 | 32 | 0 |
| Passage / 1500 | 36 | 4 | 32 | 0 |
| Passage / 3000 | 36 | 4 | 32 | 0 |
| Owner / 800 | 39 | 4 | 32 | 3 |
| Owner / 1500 | 36 | 4 | 32 | 0 |
| Owner / 3000 | 36 | 4 | 32 | 0 |

При owner 800 ещё один non-baseline witness (`mkdocs-05`) теряется после admission.
В целом корпусе: 24 claim annotations без полного literal witness в selected
source corpus, 14 discovery losses, 35 admission losses, 15 visible при 1500/3000.
Это другой знаменатель (88 annotations), не 49 previously supported claims.

**При 1500/3000 все 36 потерь baseline происходят до packing.** Переход к другому
packing objective их не исправит. Вне этого корпуса first-fit всё равно не optimum.

## Четыре discovery потери: найдено FTS, не hydrated

| Case | Witness rank в byte-bounded native order | Source | Причина |
|---|---:|---|---|
| fastapi-06 | 6 | tutorial/cors.md | Уже hydrated 2 hits этого source |
| typer-02 | 3 | tutorial/terminating.md | Уже hydrated 2 hits этого source |
| pydantic-03 | 4 | concepts/strict_mode.md | Уже hydrated 2 hits этого source |
| mkdocs-01 | 3 | user-guide/writing-your-docs.md | Уже hydrated 2 hits этого source |

Witness passages есть в indexed MATCH, проходят 2048-byte filter и входят в top12.
Их IDs присутствуют в `skipped_resource_ids`. Суммарные hydrated units на requests:
225 / 487 / 673 / 820 соответственно — ниже pool cap 2400; witness bytes также
помещаются в оставшийся budget. У каждого source уже два более ранних passages.
Следовательно, здесь причина **per-source cap=2**, не query vocabulary, не BM25
неспособность найти witness и не final DTO limit.

Решение для будущего отдельного эксперимента: разделить diversity cap **retrieval
pool** и cap **final rows**. Не увеличивать одновременно rank limit, pool budget и
final budget. В этом исследовании cap не изменён и benefit нового cap не измерен.

## 32 admission потери: что именно отказало

Числа ниже — witness-bearing proposals, не взаимоисключающие claims. У `mkdocs-03`
два найденных окна, оба отказали topic check.

| Первое observed veto research chain, owner 1500 | Количество proposals |
|---|---:|
| missing_exact_or_subject (research adapter) | 18 |
| no_local_topic_witness | 10 |
| condition_support_unavailable | 4 |
| verified_local_demand | 1 |

### A. Research adapter literal/subject veto нельзя путать с production predicate

Adapter отдельно требует exact hard terms и bound subjects **буквально в snippet**.
Production reference/qualification может интерпретировать source-bound subjects
иначе. Примеры:

- `fastapi-01`, `fastapi-07`: в witness snippet нет буквального `fastapi`;
- `httpx-01`, `httpx-07`: нет `httpx`; native read reason уже topic refusal;
- `typer-01`, `typer-07`: нет `typer.exit`;
- `pydantic-04` / `05`: нет `aliaspath` / `aliasgenerator`;
- `uv-01`, `uv-07`: нет `pip_index_url`.

На этих 18 witness proposals native `read_context_admission` тоже **не allowed**,
но причины различаются: topic, condition, missing terms/subject. Поэтому removal
только adapter check не является проверенным recovery этих facts.

**Что менять в контракте, а не threshold:** отличать identity/subject, разрешённый
trusted reference binding, от буквального requested API/literal. Не требовать
полного набора имён из bundled question от каждого partial fact. При этом нельзя
разрешить неправильный subject/condition или сертифицировать private sibling.
Новый такой механизм здесь не реализован и не принят.

### B. Topic locality отвергает найденный annotated fact

`starlette-05`, `typer-04`, `pydantic-06`, `httpx-02`, `httpx-03`, `mkdocs-03`,
`mkdocs-04`, `mkdocs-07`, `uv-05`: exact witness найден и proposed, но отказан.
Existing policy требует три query terms и соседнюю query pair в одной substantive
sentence. Это lexical locality, не общий detector полезного source context.

Решение: искать общий admission контракт для source-bound contextual passages,
а не новые pair thresholds, aliases или relation-specific исключения. Простое
удаление check неприемлемо: прежний diagnostic replay выдавал sources всем восьми
unanswerable cases. Это наблюдение про negatives, не proof нарушения source guards.

### C. Conditions и typed-local reason требуют отдельной проверки

`starlette-03`, `typer-06`, `ruff-04`, `uv-03`: witness найден, но existing applicability
veto возвращает `condition_support_unavailable`. Не снимать этот check; нужно
сопоставить request constraints с exact source context и wrong-condition mutations.

`httpx-06`: native admission возвращает `allowed=False`, reason
`verified_local_demand`. В `read_context_admission.py:89–92` допустимы только reasons
`visible_fields` / `insufficient_visible_match` от qualification; typed-local reason
до topic check отказывается. `domain/admission_contract.py` использует тот же reason
для положительного typed-local decision. Это **несовпадение reason contracts**,
не доказательство разрешённого read packet. Исправление вне этого исследования;
нельзя превращать typed proof в read permission простой whitelist строкой.

## Partial facts: все шесть потерь здесь admission, не discovery

`fastapi-07`, `httpx-07`, `starlette-07`, `typer-07`, `uv-07`: witness-bearing окна
отказываются research literal/subject check. `mkdocs-07`: topic locality refusal.
Private tail не должен требовать blanket denial известного независимого fact,
но это должно обеспечиваться request-bound partial handling, не выдачей credits
для неизвестной части. Наличие источника в packet не равно known-claim retention.

## Что сохранено / проверено

- Код audit, tests multipart/path specificity, stage attribution и DB read-only.
- **38 passed**: 9 research tests + 29 existing 01–04 API controls.
- Полные 528 claim-stage rows (88 annotations × 6 strict cells), summaries и IDs:
  `/home/viadmin/.cache/docatlas-experiments/grounded-loss-audit-20261003-03/`.
- `claims.json`: every claim, witnesses, missing terms, reasons, discovery ranks.
  `summary.json`: six cells. `provenance.json`: input/code/protocol identities.
- Input `results.json` SHA256:
  `3ce077baf0324833bea080c55bf7de9c62a9f5184ba3a309258ae826c86818fb`.
- Current replacement **REJECTED FOR ROLLOUT**, 01–04 **RETAINED ISOLATED**.
  Исходники 01–04 уже сохранены в существующем checkout/commits, не переписаны.

Повторение (новый output):

```bash
PYTHONPATH=. /usr/bin/python3.12 v2plan/grounded_loss_audit.py --input /home/viadmin/.cache/docatlas-experiments/grounded-budget-20261003-06 --output /home/viadmin/.cache/docatlas-experiments/grounded-loss-audit-NEW
/usr/bin/python3.12 -m pytest -q tests/docs/test_grounded_budget_probe.py tests/docs/test_source_window_eligibility.py tests/test_retrieval_passages.py tests/test_retrieval_passage_index.py tests/test_lexical_passage_retrieval.py
```

Неизвестные equivalences, cross-owner restrictions и comprehensive guard/negative
matrix остаются вне доказанного результата. Не заявлять semantic completeness,
production regression Green или готовый новый admission. Runtime, frozen gold,
public defaults и чужие experiments не менялись. Auto-commit/rollout не выполнялись.
