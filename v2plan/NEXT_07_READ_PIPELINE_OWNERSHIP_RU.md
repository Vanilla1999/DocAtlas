# 07. Проверить причины потери read context и выбрать одну замену

Статус: **PLANNED; runtime trial не выбран; исправление не выполнено**.
Дата: 2026-10-04. План создан по запросу пользователя, не разрешает rollout.

## 0. Задача и самокритика

Задача: объяснить потерю LeaseClient timeout/exception в полном native pipeline,
определить одну ошибочную ответственность и проверить её замену без новых rescue.
Если исправление требует нескольких одновременно изменяемых слоёв — остановить
implementation, записать границы зависимостей. Не выдавать анализ за исправление.

Что было слишком уверенно в предыдущем выводе:

1. **«Два решения расходятся, значит одно лишнее» — неверно.** Qualification
   оценивает соответствие query, read-admission — допустимость partial window.
   Сравнивать можно только одинаковые request/source/span, scope и полномочия.
2. **«Compiler не умеет разделить вопрос» — неточно.** `retrieval_needs()` уже
   выделяет default и exception. `compile_need_contracts()` в этом случае создаёт
   один unresolved requested_part. Первый разбор эвристический; переносить его
   результат в trusted applicability без проверки нельзя.
3. **«Одна admission-правка исправит LeaseClient» — опровергнуто диагностикой.**
   Даже после временного пропуска condition/locality в read route оба документа
   доходят до projector, но packet содержит overview. Общий read fallback в core
   вызывается при пустых sources; специальные proposals имеют другой путь.
   Это описание конкретного пути, не утверждение, что все supplements запрещены.
4. **«Один pool/selector» — цель, не алгоритм.** Как отличать полезное дополнение
   от дубля и не вытеснять факты, пока не установлено. Нельзя писать новый framework
   под этот лозунг. Qualification содержит typed witnesses, не только overlap.
5. **«Меньше проверок = лучше» — неверно.** Повторная проверка изменённых bytes
   обязательна. Повторную подготовку одинаковых окон можно исследовать отдельно,
   но такой refactor не доказывает recovery фактов.

История, обязательная к чтению до правки:
- `NEXT_02_ADMISSION_SIMPLIFICATION_RU.md`: удаление `no_new_direction` дало
  recovery synthetic controls, но **49 → 45** frozen claims. Вариант отклонён.
- `UNIFIED_READ_RESULT_RU.md`: isolated read **11 → 11** при budget 1500 — не
  parity с полным native pipeline на 800. Unified replacement не принят.
- `ADMISSION_REMOVAL_DECISION_RU.md`: source guards не заменяют relevance,
  расхождение verdicts не доказывает избыточность всех veto.
- `docs/adr/0003-context-first-project-reads.md`: partial context допустим,
  но docs_context не даёт answer/edit authority. ADR не задаёт готовую политику
  unknown condition scope. Docs о generated aliases могут описывать старый путь;
  текущего producer проверять по коду, не объявлять весь документ неверным.

## 1. Правила исполнения для модели

1. Выполнять этапы A → B → C → D → E. Следующий этап разрешён только после DONE
   предыдущего. Заполнять журнал в конце **этого** документа.
2. Сейчас разрешены observer, fixtures и analysis. Runtime trial разрешён только
   после заполненного решения C. Новый product contract не принимать молча.
3. Один trial = одна ответственность в одном слое: compiler **или** admission
   **или** selector. Retrieval, budgets, ranking и другие слои фиксированы.
   Механический refactor выполняется отдельно и не считается defect fix.
4. Не добавлять OR fallback, rescue, relation/library exceptions, aliases,
   словари синонимов, semantic model, новый compiler или threshold tuning.
5. Не удалять guards, не заменять их флагами `qualified/context_eligible`.
   Source/security/version/scope/freshness/span/request, identity, exact и
   applicability сохраняются. Unknown не становится applicable.
6. Не изменять failing expectations LeaseClient, frozen corpus/labels, limits,
   CI markers, skips/xfails ради PASS. Explicit lookup не заменяет root-only test.
7. Не трогать 81 UNRESOLVED node, runner/provider, historical gate migrations
   и публикацию: это незавершённый план 06, не scope 07.
8. Не использовать gold claims, имена fixtures или ожидаемые числа в runtime.
   Они доступны только evaluator после получения packet.
9. Existing dirty files — baseline/user work. Не reset/stash/clean, не коммитить
   автоматически. Research substitutions только внутри process/context manager;
   production/defaults автоматически не переключать.
10. Один кандидат после C. При потере claim, нарушении guard или необходимости
    второй policy-правки — REJECTED/BLOCKED, сохранить данные и остановиться.
    Техническую ошибку harness можно исправить, сохранив invalid run; это не
    повод повторять valid неудачу с подстроенными параметрами.
11. Не создавать новый eval engine. Использовать existing observers, index,
    assessor и validator. Подмена gate для диагностики не является кандидатом.
12. Нет подтверждения — писать `unknown/not_run`, а не PASS. Результаты на
    просмотренных fixtures — development evidence, не blind/held-out оценка.

## A. Зафиксировать baseline и воспроизвести потерю

### A1. Provenance

Из корня repo записать в новый `v2plan/artifacts/next07/<run-id>/`:
commit, `git status --short`, tracked diff, hashes untracked файлов, hashes
изменяемых runtime modules, corpus/protocol и точные команды. Не включать secrets.
Не перезаписывать старый каталог. Для временных DB использовать `/tmp/opencode`.

Команды наблюдения:

```bash
git rev-parse HEAD
git status --short
git diff --stat
git diff --check
```

### A2. Native baseline, без подмен и дополнительных lookup

```bash
DOCATLAS_OFFLINE=1 .venv/bin/pytest -q \
  tests/docs/test_read_context_admission_boundary.py \
  tests/docs/test_admission_guard_composition.py \
  tests/docs/test_evidence_set_disposition.py \
  tests/docs/test_need_local_admission.py \
  --junitxml=/tmp/opencode/next07-baseline-focused.xml
```

Последнее наблюдение: 74 PASS / 2 LeaseClient FAIL. Не вписывать эти числа как
новый результат. Перенести новый XML и log в artifacts; exit=1 не скрывать.

### A3. Разделить синтаксис и applicability

Выполнить этот diagnostic код, сохранить stdout. Это **не новый test contract**:

```python
from dataclasses import asdict
from docmancer.docs.domain.question_retrieval_needs import retrieval_needs
from docmancer.docs.domain.need_contracts import compile_need_contracts
from docmancer.docs.domain.query_reference_binding import ScopeKey, resolve_references

question = (
    "What is LeaseClient default timeout duration for requests and "
    "which exception is raised when an operation expires?"
)
references = resolve_references(
    question, catalog=(), scope=ScopeKey("diagnostic", "", "snapshot-1"),
)
print([asdict(row) for row in retrieval_needs(question)])
print([asdict(row) for row in compile_need_contracts(question, references)])
```

Пустой catalog проверяет только syntax. Для выводов о source binding использовать
actual `_reference_root_plan` из native capture, а не этот diagnostic ScopeKey.

**DONE A:** новая native потеря воспроизведена; оба параметра 17/LeaseExpired и
29/WaitExpired учтены; baseline provenance и выходы сохранены. Если поведение
изменилось — сначала объяснить delta, не применять старый диагноз автоматически.

## B. Карта решений на одних и тех же данных

### B1. Где наблюдать

| Слой | Функции / файлы | Что записать |
|---|---|---|
| Retrieval | `_project_docs_service_part03.py`: `query_project_docs`, `SourceReferenceContext.prepare` | Query, filters, полученные source IDs, исходные bytes и bounds |
| Query qualification | `evidence_qualification.qualify_evidence`, `admission_contract.choose_need_admission` | Query scope, exact/subject checks, matched terms, typed/legacy route, reason |
| Read proposals | `read_context_admission.iter_prefit_context_variants`; `need_context_projection.preferred_context_variants` | Какие окна предложены, condition/locality verdict, кто не создал proposal |
| Early removal | `project_doc_ranking.rerank_project_doc_chunks`; `_project_context_service_part01.py` | Before/after, context_candidate_ids; qualification reject отдельно от caps/budget |
| Final selection | `_docs_context_projection_core.project_docs_context` и `ProjectionDecisionTrace.record` | Actual attempted window, rejection/acceptance, занят ли packet, почему fallback пропущен |
| Final boundary | `docs_context_projection.project_docs_context`, public handler | После supplements: sources, restrictions, flags, validator, budget |

Одна строка трассы: request hash + project/version/snapshot + canonical path +
content hash + точный `[start,end)` + query/need ID + stage + outcome + reason.
Если span отсутствует, записать `unknown`; не восстанавливать его первым
`raw.find(snippet)` — в документе могут быть повторяющиеся фразы.
Различать `rejected`, `not_proposed`, `not_reached`, `budget_limited`.

Пример observer: выполнить после A3 в том же script (`question` уже определён).
Делегирует исходной функции, не меняет результат.

```python
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
from docmancer.docs.application import read_context_admission as module
from tests.docs._global_evidence_fixtures import capture_fixture

events = []
original = module.read_context_admission

def observe(candidate, **kwargs):
    decision = original(candidate, **kwargs)
    events.append({
        "path": candidate.get("path"),
        "span": candidate.get("char_span"),
        "snippet": candidate.get("snippet"),
        "allowed": decision.allowed,
        "reason": decision.reason,
    })
    return decision

documents = {
    "default.md": "# LeaseClient\n\nThe default timeout is 17 seconds.\n",
    "error.md": "# LeaseClient\n\nAn expired operation raises `LeaseExpired`.\n",
    "overview.md": "# Overview\n\nLeaseClient default timeout duration "
                   "requests exception operation behavior documentation.\n",
}
with TemporaryDirectory(dir="/tmp/opencode") as directory:
    with patch.object(module, "read_context_admission", observe):
        capture = capture_fixture(Path(directory), documents, question)
assert events, "observer was not reached"
print(events)
print(capture["public_payload"])
```

Остальные поля identity добавить из actual prepared candidate в полную трассу.
Для bypass arms B2 использовать `capture_public_call` напрямую: сохранить
validator errors, которые `capture_fixture` иначе остановит assertion-ом.
Сначала native positive fixture,
затем source/request damage controls; пустой pipeline не доказывает работу guard.

### B2. Ограниченная причинная диагностика

Повторить четыре arms на одинаковом request/corpus, budget 800 и cap 3:

1. Native без подмен.
2. Только read `_applicable_context` временно возвращает True.
3. Дополнительно только read `local_topic_witness` временно возвращает True.
4. Отдельно от 2–3: только rerank получает все текущие candidate IDs как exemptions.

Arms 2–4 намеренно отключают проверки и **никогда не являются безопасным fix**.
Не переносить подмены в runtime. Записать, что arm 3 — последовательный
диагностический bypass двух veto одного read route, не допустимый patch trial.
Остальные lanes не менять. Сохранить полные captures и validation errors.

Проверяемая гипотеза из предыдущего анализа: 2 останавливается на locality;
3 и 4 сохраняют factual candidates до projector, но final оставляет overview.
Нельзя считать отсутствующий final факт прямым доказательством конкретного veto:
нужен actual selection event или подтверждённое `not_proposed/not_reached`.

Дополнительный прежний arm «убрать overview и пропустить оба veto» дал invalid
projection: отсутствовали authority/project_identity/scope. Это не recovery PASS
и не native regression. Сохранить как ограничение диагностической подмены;
не чинить serializer в рамках этого исследования.

### B3. Проверить три области действия условия

До нового runtime trial зафиксировать fixtures и expected visible facts:

| Ситуация | Вопрос / источники | Допустимый final результат |
|---|---|---|
| Условие только второй части | Исходный LeaseClient вопрос; отдельные default и expired-operation docs | Default и exception доступны вместе со своим subject; нельзя перенести условие expiration на default или потерять его у exception |
| Условие всего вопроса | `When preview is disabled, what is RelayClient default timeout and which exception is raised?`; источники с explicit disabled/enabled clauses | Только применимые disabled facts с сохранённым условием; enabled факт не выдавать как ответ о disabled |
| Область действия неизвестна | `What is RelayClient default timeout and which exception is raised, only for administrators?`; source содержит только безусловный default | Не объявлять applicability/full support. Разрешено ли такое окно как read context — **открытый контракт**, а не автоматически empty или automatically allowed |

Добавить controls к тем же fixtures: отсутствует второй факт; чужой subject;
wrong/missing state; restriction после factual sentence; clipped restriction;
точный identifier/version не совпадает; unsafe/stale/snapshot/request mutation.
Для restriction использовать явный текст, например `Only when preview is disabled.`
в исходном source; clipped вариант должен действительно удалять эту строку.
Проверять final bytes и source scope, а не только `answer_supported=false`.

По неизвестному scope выписать конкретный допустимый/недопустимый packet и
основание из принятого контракта. Если основания нет — BLOCKED на C, вынести
один конкретный policy-вопрос пользователю. Не сочинять новое правило самому.

**DONE B:** таблица stages заполнена для обоих factual sources и overview;
различены все veto, отсутствие proposals и scope; три ситуации сопоставлены;
каждый вывод помечен `observed`, `code-derived` или `hypothesis` с артефактом.

## C. Выбрать ровно одну ответственность либо остановиться

Заполнить перед implementation:

```text
trial_type: behavior_preserving_refactor | behavior_fix
layer: compiler | admission | selector
removed_responsibility: <конкретная функция/ветка и её прежнее решение>
remaining_owner: <существующий владелец, не новый wrapper над всеми veto>
replacement_rule: <общее правило без case names и новой grammar>
contract_basis: <accepted doc/test; новый policy-вопрос должен быть решён явно>
positive_final_packet: <что станет видно и почему>
negative_controls: <IDs и запрещённые bytes/permissions>
allowed_files: <точный список>
unchanged_layers: <остальные слои>
stop_condition: <как обнаружить необходимость второй policy-правки>
```

Возможные результаты, не автоматическая очередь патчей:

- **Compiler:** выяснить, должен ли enrichment сохранять найденные части без
  повышения их interpretation до supported. Сам факт двух RetrievalNeed этого
  не доказывает. Если locality/selection всё равно блокируют delivery, такой
  patch нельзя объявить исправлением LeaseClient.
- **Admission:** заменить одну конкурирующую read-политику только при полном
  контракте applicability/locality и доказанном участии разрешённых окон в final.
  Не решать проблему простым `return True` или 3 terms → 2 terms.
- **Selector:** допустимо исследовать замену выбранной ответственности только
  если окна уже законно admitted. Нельзя принять bypassed arms B2 как такой вход.
  Не повторять удаление `no_new_direction`: известны четыре потери из плана 02.
- **Mechanical:** повторные проходы `iter_need_context_variants` в precedence/set
  могут быть объединены лишь при сохранении порядка, окон, dispositions и
  diagnostics. Упрощение не обещает новый recall; не выполнять его вместо fix
  без явного выбора этого результата.

**DONE C:** выбран один trial с существующими законно admitted positives и
полным правилом; пользовательские решения о новом контракте зафиксированы.
**BLOCKED:** один слой не может обеспечить заявленное исправление. Указать
независимые необходимые изменения, не выполнять их общим patch. Закончить анализ
и предложить точную границу следующего решения, не запускать ещё один поиск policy.

## D. Изолированная реализация выбранного trial

1. Использовать отдельный research candidate / отдельный patch поверх сохранённого
   dirty baseline. Не подключать его к production/defaults. Не переносить сюда
   historical unified compiler/renderer как будто это existing native behavior.
2. Добавить минимальный regression test именно выбранной обязанности, плюс
   negative controls B3. Для fix сначала получить meaningful FAIL на baseline.
   Для mechanical refactor требовать parity, не искусственно создавать bug test.
3. Заменить выбранную ветку; не оставить старый veto и не добавить новую OR lane.
4. Запустить focused tests. Проверить diff на новые budgets, grammar, fallback,
   source reads, approvals, runtime fixture names и изменение второго слоя.
5. Если native defect остаётся, записать оставшуюся стадию. Не расширять patch
   до следующего слоя. Уточнение hypothesis не является PASS fix.

Минимальная проверка native цели (existing helper; не assisted-запрос):

```python
from tests.docs._global_evidence_fixtures import capture_fixture, visible

def assert_lease_delivery(tmp_path, value, error):
    capture = capture_fixture(tmp_path, {
        "default.md": f"# LeaseClient\n\nThe default timeout is {value} seconds.\n",
        "error.md": f"# LeaseClient\n\nAn expired operation raises `{error}`.\n",
        "overview.md": "# Overview\n\nLeaseClient default timeout duration "
                       "requests exception operation behavior documentation.\n",
    }, "What is LeaseClient default timeout duration for requests and "
       "which exception is raised when an operation expires?")
    text = visible(capture)
    assert f"{value} seconds" in text
    assert f"An expired operation raises `{error}`." in text
    assert all(capture["public_payload"][key] is False
               for key in ("answer_supported", "answer_available", "edit_ready"))
```

Использовать оба существующих параметра; не заменять existing test этим helper.
Helper уже проверяет source bounds, schema, 800 tokens и ≤3 sources. Дополнительно
проверить subject binding и restrictions по captured source. Появление числа
в другом документе или другой версии не выполняет assert по смыслу.

Новые test roots регистрировать по existing diagnostic manifest rules, label
`behavioral` для runtime checks. Hash обновлять только из фактического inventory;
не менять labels/markers существующих failures.

**DONE D:** одна обязанность заменена; regression и guards проходят; нет diff
второго policy-слоя. Сокращение показать конкретно: какая ветка/повторный проход
исчезли. Новый wrapper без удаления ответственности не считается сокращением.

## E. Приёмка candidate, не выпуск

### E1. Fresh paired native replay

Использовать existing `load_protocol`, `documents_for`, `isolated_service`,
`index_project`, `observe_call`, `assess_context`, `audit_payload`.
Пример группировки/сохранения arms есть в `selection_direction_ablation.py`;
**не вызывать его `candidate_function()`**: он повторяет отклонённое удаление.
Не использовать старую reference read-function как весь current baseline.

- 80 frozen cases: одинаковый corpus/index/config на baseline и candidate arm;
  одна зафиксированная candidate policy, root questions неизменны.
- Четыре controls `both/partial/absent/wrong` из `lookup_gap_probe.py`: сохранить
  исходные native/assisted lanes отдельно; результат assisted не заменяет native.
- B3 и LeaseClient: отдельный development inventory, не прибавлять к 49 claims.
- Сохранить полные packets, snapshots, validator errors, assessment и traces.
  Budget **800**, cap **3**; без исследования сетки 800/1500/3000.

Проверять IDs, а не равенство суммы:

```python
def supported_ids(rows):
    return {
        (row["case_id"], claim_id)
        for row in rows
        for claim_id, result in row["assessment"]["claims"].items()
        if result["status"] == "supported"
    }

# rows — явно нормализованный summary existing assessor, не его raw schema.
lost = supported_ids(baseline_rows) - supported_ids(candidate_rows)
gained = supported_ids(candidate_rows) - supported_ids(baseline_rows)
assert not lost, sorted(lost)
```

Исторические 49 IDs также сверить с сохранённой приёмкой next04/next05. Если
fresh baseline уже их потерял, это отдельный blocker, а не разрешение понизить
планку. Сохранять полезные partial facts, даже если весь case не `sufficient`.
Changed snippets проверить по смыслу с exact source citations; `needs_review`
не считать ни автоматически PASS, ни автоматически ложным ответом.
New negative sources разобрать по действующему frozen contract; при нарушении
отклонить candidate, не менять label unanswerable или expected empty packet.

### E2. Guards и общий regression

Повторить A2 с подключённым isolated candidate; добавить existing модули:

```text
tests/docs/test_shared_context_proposals.py
tests/docs/test_evidence_set_context_delivery.py
tests/docs/test_evidence_set_delivery_acceptance.py
tests/docs/test_requested_evidence_retention.py
tests/docs/test_source_window_eligibility.py
```

Pre-existing failures сравнить по node IDs с fresh baseline; не исключать их
из запуска. Changed reason/count при unchanged forbidden outcome не доказывает
сохранение guard: нужны положительные и повреждённые inputs, clipping и budgets.

Только если E1 и focused candidate checks не выявили регрессий, выполнить один
full offline run **в checkout/process, где действительно исполняется candidate**:

```bash
DOCATLAS_OFFLINE=1 .venv/bin/pytest tests/ -m 'not live and not live_network' -q \
  --junitxml=/tmp/opencode/next07-candidate-full.xml
```

In-memory monkeypatch из завершившегося script не действует на новый pytest.
Зафиксировать механизм подключения candidate и hashes; иначе run = baseline,
не candidate verification. Для отдельного checkout перенести полный сохранённый
baseline patch/untracked inputs, не только HEAD. Не потерять работу пользователя.

Для runtime candidate повторить existing checks согласно актуальному CI:
recovery contract/mutation, agent-developer/adversarial (включая mutation),
question-surface, schema/footprint и stdio smoke. Точные команды/CLI взять из
текущих scripts/workflows до запуска; не выдумывать flags.
Красные gates из 06 остаются красными. Namespace/model blockers не лечить здесь.

**DONE E:** нет lost required IDs/partial facts, новых forbidden packets,
source/condition/schema/budget/permission regressions или новых failing nodes;
все changed packets разобраны. Target outcome выбранного trial выполнен.
Известные required blockers записаны отдельно; локальная parity их не закрывает.

## Итоговые критерии и остановка

| Статус | Условие |
|---|---|
| ANALYSIS_COMPLETE / IMPLEMENTATION_BLOCKED | A–B выполнены; C объясняет, почему одного допустимого trial нет. Это завершённое исследование, **не исправление** |
| REFACTOR_VALIDATED_LOCAL | Выбран mechanical trial; доказаны parity и реальное сокращение. LeaseClient defect остаётся открытым |
| FIX_VALIDATED_LOCAL | C–E выполнены; оба native LeaseClient tests и B3 проходят без помощи lookup, выбранная ответственность заменена, факты/guards сохранены |
| REJECTED | Есть regression, false applicability/support, потеря обязательного факта, новый rescue/threshold или изменение нескольких слоёв |
| NOT_DONE | Не хватает capture, unknown contract, не выполнен необходимый check или changed packet не разобран |

Даже FIX_VALIDATED_LOCAL не означает release READY: план 06, required gates,
runner isolation и модельная приёмка остаются отдельными обязательствами.
После первого доказанного regression не запускать дорогие проверки ради суммы
PASS и не подбирать второй вариант автоматически.

## Журнал исполнения

Заполнять здесь, прошлые результаты не перезаписывать:

```text
run_id / baseline commit+patch hashes:
A: NOT_RUN / artifact paths:
B: NOT_RUN / observed vs hypotheses:
C: NOT_SELECTED / owner, rule, allowed files, contract decision:
D: NOT_RUN / removed responsibility:
E: NOT_RUN / claim IDs, partial facts, negative packets, guards, test delta:
verdict:
LeaseClient fixed: yes | no | not_verified
remaining plan-06 blockers:
next action: <одно действие либо STOP с точной причиной>
```
