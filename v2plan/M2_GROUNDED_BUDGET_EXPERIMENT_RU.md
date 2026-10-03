# M2: Grounded-style experiment — что покупает budget до 3000

2026-10-03. **Исполнительный план, не результат эксперимента.**
Работать в текущем проекте `/home/viadmin/StudioProjects/hermes/docmancer`.
Не переносить сессию/worktree в `/tmp/opencode`. Не начинать с checkpoint/коммита
или нового Gate A approval: следующий запрос на исполнение начинается с теста.

## 1. Решения для этого эксперимента

1. Оставить implemented 01–04: source eligibility, contextual passages, index,
   native FTS5 BM25. Не переписывать retrieval и не подключать второй сервер.
2. Старый `gate_a_candidate.py` не доделывать и не использовать как candidate
   predicate/solver. Его B1/B2 Reds сохранить как историю отклонённого решения.
3. Сравнить **800 / 1500 / 3000 whole-DTO admission units**. Это три заранее
   выбранных экспериментальных значения, не production defaults и не tokenizer tokens.
4. Выбрать простой rank-ordered first-fit selector. Он **не глобально оптимален**.
   Потерю из-за этого измерить, а не скрыть под прежним objective.
5. Сравнить два способа доставки: intact passage и intact owning section.
   Никаких «следующий paragraph похож на restriction» regex.
6. Все результативные оценки делать по **финальному serialized DTO**, не candidate
   pool. Окно без доказанных bindings не доходит даже до diagnostic packet.

**Вопрос эксперимента:** можно ли купить retention большим packet и простыми
source boundaries; если нельзя — какая конкретная обязанность мешает?

### Что можно пожертвовать в isolated experiment

| Обязанность | Решение |
|---|---|
| Лимит 800 | Поднять до 1500/3000 только в runner |
| Глобально лучший packet | Заменить на deterministic first-fit; показать потери |
| Компактность snippet | Доставлять полный owner, когда он помещается |
| Поддержка любой формы документа | Назвать supported/unsupported формы по результатам |
| Строгая topic relevance | Только отдельный diagnostic replay; false admissions — failures, не PASS |
| Source/security/freshness/version/scope/path/request/span/digest | **Не жертвовать** |
| Hard subject/literal/condition; negation/exception preservation | **Не жертвовать** |
| Proof/edit permission | **Не выдавать из read context** |
| Existing negatives/partial facts | Не менять assertions/gold; все потери перечислить |

Production остаётся на прежнем маршруте и 800 units / ≤3 source rows.
Запрос пользователя разрешает исследовать больший budget, а не rollout.

## 2. Allowed files и реальные API

Создать только:

- `v2plan/grounded_budget_probe.py` — research code + CLI;
- `tests/docs/test_grounded_budget_probe.py`;
- `tests/diagnostic_labels.grounded_budget_probe.json`;
- `v2plan/GROUNDED_BUDGET_RESULT_RU.md`.

Не менять `docmancer/`, старые tests, frozen corpus, evaluator, defaults, lockfiles
и чужую `experiments/crosslingual_relevance/`. Никаких aliases, rewrites, моделей,
relation-specific rescues, новых floors/pairs или threshold tuning.

Переиспользовать:

```python
from docmancer.core.models import Chunk, Document
from docmancer.core.sqlite_store import SQLiteStore
from docmancer.core.retrieval_passages import PassageProfile
from docmancer.core.structured_chunking import parse_markdown_parents, _atom_spans
from docmancer.docs.application.source_reference_evidence import SourceReferenceContext
from docmancer.docs.domain.source_window_eligibility import source_window_eligibility
from docmancer.docs.domain.documentation_query_plan import build_documentation_query_plan
from docmancer.docs.application.read_context_admission import read_context_admission
from docmancer.docs.application._docs_context_payload import _payload
from docmancer.docs.application.model_visible_projection import (
    DOCS_CONTEXT_SOURCE_FIELDS, _snapshot_entry, _source_digest,
    validate_model_visible_projection,
)
from docmancer.docs.application.model_visible_projection_helpers import (
    canonical_projection_bytes, docs_context_budget_tokens,
)
from eval.evidence_quality_v2.run import load_protocol, documents_for, registry_for
from eval.evidence_quality_v2.semantic import assess_context
```

`decide_read_window()` — stub, не использовать. `source_window_eligibility()`
проверяет binding, **не relevance/applicability**. `read_context_admission()`
переиспользуется как unchanged conservative control, не объявляется новым общим
semantic predicate. Existing condition grammar остаётся ограниченной.

## 3. Начать с budget-теста, а не с изменения константы

**Создать behavioral test:** один неизменный validated DTO помещается в 3000,
но не в 800. Snippet — exact source slice, metadata и query plan сохранены.
Взять источник с code + внешним restriction, около 5000 UTF-8 bytes, внутри
одного owner. Проверить `800 < docs_context_budget_tokens(payload) <= 3000`.

Требуется **Red нового экспериментального selector**, затем минимальный Green.
Отсутствующий файл/import/label — setup error, не behavioral Red; сначала stub.

Не изменять `PROJECT_CONTEXT_BUDGET`, `DOCS_CONTEXT_MAX_TOKENS` или исторический
solver cap. У `validate_model_visible_projection(..., max_tokens=budget)` уже есть
параметр: передавать реальное значение 800/1500/3000.

### Отдельные лимиты: не спутать их с DTO budget

| Граница сейчас | Правило эксперимента |
|---|---|
| `query_passages`: limit ≤20, passage ≤2048 bytes, pool ≤2400 units, per-source ≤2 | Сохранить одинаковыми во всех прогонах |
| Source/window inventory | Максимум 4096 proposals; один inventory на case, не на budget |
| `_docs_source`: snippet ≤3000 **characters** | Не использовать для больших research rows; см. builder ниже |
| Experimental owner proposals | ≤12000 UTF-8 bytes суммарно materialized proposal text на request |
| DTO | Реальный counter, budget 800/1500/3000, source rows ≤3, per-source rows ≤2 |

12000 bytes — **новый явно названный experimental envelope**, не утверждение,
что прежний Gate R уже разрешал owner expansion. Он одинаков для трёх budgets.
Не считать его лимитом на full raw snapshots: отдельно измерить их unique bytes
и metadata bytes. Raw documents могут быть больше; не скрывать это в packet cost.

Если cap отрезал proposal, reason `proposal_byte_cap`, не `irrelevant`.
Если passage pool потерял witness, повышение **финального** budget этого не исправляет.
В этом эксперименте не увеличивать одновременно candidate/hydration/index limits.

## 4. Один request-bound inventory; две delivery policies

Runner грузит frozen corpus через `load_protocol()` / `documents_for()`.
Индексировать **только source files**, не cases/witness annotations. В пределах
каждого project group одинаковый corpus/index обслуживает все его cases/budgets.

1. Создать отдельный fixture corpus/state вне checkout, без user storage.
2. Создать opt-in `SQLiteStore(..., passage_profile=PassageProfile())` на fixture DB.
   Metadata брать из существующего fixture ingest/current catalog: project identity,
   project path, canonical relative path, content hash, authority, scope/version,
   lifecycle/freshness. Не подставлять значения ради прохождения guards.
3. Вызвать `query_passages(case['question'], filters=...)` **один раз на case**.
   Сохранить original question, SQL trace, native rank и resource omissions.
4. Подготовить `SourceReferenceContext` на этом же store/generation/request.
   Разрешение источника и явные path/module/version filters сохраняются.
5. Получить original bytes только из allowed immutable indexed snapshot.
   Source cache — один на request. Никаких file/network reads на alternative.
6. Сформировать policies P/O ниже, дедуплицировать exact source spans. Owner,
   достигнутый несколькими hits, получает **первый native rank**, не boost.
7. Создать `Chunk` с буквальным `raw[start:end]` и правильными metadata/span/hash;
   пропустить через `SourceReferenceContext.prepare()`. Не расширять готовый
   `_reference_evidence` простой заменой `char_end`: reference envelope должен
   заново происходить из trusted generation. Проверить eligibility после prepare.

**P — intact passage, diagnostic control.** Только весь исходный search passage.
Не вырезать intro/fence/row/item и не наследовать approval после clipping.
P **не гарантирует** внешние restrictions: near-cap B1 должен выявить эту потерю.
Packet P с потерянным restriction не считается acceptable candidate.
Все P rows пометить в result metadata `diagnostic_only=true`,
`eligible_for_rollout=false`; это control, не разрешение потерять restriction.

**O — conservative owner, основной candidate.** Если passage пересекает code/list/
table atom — предложить целиком один existing owning section по source parser.
При отсутствии structured atom оставить весь passage. Ordinary prose не становится
обязательным full-parent snippet. Не склеивать соседние owners или holes.
Если owner не разрешён filters/scope — отказ. Если не помещается — отказ, без
fallback к command-only snippet. Unsupported/unclosed structure → unknown.

Это проверка дешёвого консервативного способа, **не detector semantic completeness**.
Restrictions между owners или explicit dependencies вне разрешённого extent
остаются unresolved; отсутствие graph edge не доказывает отсутствие зависимости.

Одинаковые proposals/query plan/metadata каждого policy использовать при всех
трёх budgets. Gold не участвует в выборе policy, owner, окна или порядка.

## 5. Минимальный research DTO builder без скрытого 3000-char cap

Поместить в `grounded_budget_probe.py`. Вызвать **только после** source, hard
subject/literal/condition и structural checks; builder не разрешает чтение.
`item` — заново prepared window, не публичный legacy row с approval flags.

```python
import hashlib


def render_row(item):
    ref = item['_reference_evidence']
    start, end = item['char_span']
    text = ref['raw_document'][start:end]
    if item['snippet'] != text:
        raise ValueError('source_window_mismatch')
    line_start = ref['raw_document'].count('\n', 0, start) + 1
    line_end = ref['raw_document'].count('\n', 0, end) + (
        0 if text.endswith('\n') else 1
    )
    identity = (ref['source'], item['generation_id'], start, end)
    row = {
        'evidence_id': 'ev-' + hashlib.sha256(
            canonical_projection_bytes(identity)).hexdigest()[:16],
        'path_or_url': ref['source']['canonical_path'],
        'section': str(item.get('heading_path') or item.get('title') or 'document'),
        'snippet': text,
        'version_binding': str(item.get('version_binding') or
                               item.get('resolved_version') or 'unversioned'),
        'content_sha256': _source_digest(item),
        'project_identity': item['project_identity'],
        'line_start': line_start,
        'line_end': line_end,
        'authority': item['authority'],
        'scope': item.get('scope') or item['doc_scope'],
    }
    if set(row) != DOCS_CONTEXT_SOURCE_FIELDS:
        raise ValueError('invalid_research_source_schema')
    if (not text.strip() or len(row['path_or_url']) > 500
            or len(row['section']) > 300 or len(row['version_binding']) > 100):
        raise ValueError('source_field_limit')
    return row


def render_packet(items, *, query_plan):
    rows = [render_row(item) for item in items]
    payload = _payload(rows, query_plan=query_plan)
    snapshot = {row['evidence_id']: _snapshot_entry(item, row)
                for item, row in zip(items, rows)}
    return payload, snapshot
```

Empty `_payload([])` можно посчитать как diagnostic envelope overhead, но нельзя
выдать как successful packet. На пустом selection возвращать `payload=None`.
`_source_digest` — existing evidence-material digest; full-document digest отдельно
проверяет source eligibility. Не заменять одно другим.

Query plan во всех research cells:
`build_documentation_query_plan(case['question']).as_payload()`.
Для synthetic cases тот же planner над original question. Frozen suite не получает
добавленных lookup queries; explicit filters происходят из request/source policy,
не из `allowed_paths`/witness annotations evaluator.
Не удалять facets/recovery/metadata ради fit. Сравнение с legacy producer отдельно:
новая assembly — research DTO, не native public-route delivery.
Проверки path/section/version sizes сохраняются; снят только отдельный snippet
character cap для research serialization, не public schema или source policy.

## 6. Selector: один проход, actual DTO cost, без optimum claim

Сначала behavioral Red: 15 candidates / 30 alternatives не должны обнулить весь
feasible context из-за combinatorial exhaustion. В тесте cost — настоящая сборка
`render_packet()` и `docs_context_budget_tokens`, не `lambda packet: 100`.

Код для `grounded_budget_probe.py`; `check(item)` — pure checks из шага 7.
`proposal_id` связывает policy/source/generation/start/end, не incoming approval.

```python
def ordered_packet(proposals, *, budget, check, build):
    if budget not in (800, 1500, 3000) or len(proposals) > 4096:
        raise ValueError('invalid_experiment_limits')
    ordered = sorted(proposals, key=lambda p: (
        p['native_rank'], p['proposal_id']))
    chosen, trace, seen = [], [], set()
    for proposal in ordered:
        pid = proposal['proposal_id']
        if pid in seen:
            raise ValueError('duplicate_proposal')
        seen.add(pid)
        event = {'proposal_id': pid, 'native_rank': proposal['native_rank']}
        reason = check(proposal)
        if reason is not None:
            event['reason'] = reason
        elif len(chosen) == 3:
            event['reason'] = 'source_row_limit'
        elif sum(p['source_identity'] == proposal['source_identity']
                 for p in chosen) == 2:
            event['reason'] = 'per_source_limit'
        else:
            trial, _ = build(chosen + [proposal])
            event['dto_units'] = docs_context_budget_tokens(trial)
            if event['dto_units'] > budget:
                event['reason'] = 'dto_budget'
            else:
                chosen.append(proposal)
                event['reason'] = 'selected'
        trace.append(event)
    # Снова проверить exact final bytes; никто не читает cached allowed flag.
    if any(check(p) is not None for p in chosen):
        return {'status': 'final_recheck_failed', 'payload': None,
                'trace': trace, 'visits': len(trace)}
    if not chosen:
        return {'status': 'no_admissible_packet', 'payload': None,
                'trace': trace, 'visits': len(trace)}
    payload, snapshot = build(chosen)
    errors = validate_model_visible_projection(
        payload, snapshot=snapshot, max_tokens=budget)
    if errors or docs_context_budget_tokens(payload) > budget:
        raise ValueError({'invalid_final_packet': errors})
    assert not payload['answer_supported'] and not payload['edit_ready']
    return {'status': 'completed_first_fit', 'payload': payload,
            'snapshot': snapshot, 'trace': trace, 'visits': len(trace)}
```

`build(proposals)` преобразует prepared `proposal['item']` через `render_packet`.
Никаких I/O/URI registrations внутри `check`/`build`. Visits считают rejected
proposals тоже. Дополнительно логировать check_calls, build_calls, parsed atoms,
source bytes и время: одна visit не равна постоянной стоимости обработки текста.

Проверить permutation/stable ties, ≤3 rows / ≤2 per source, Unicode/repeat identity,
первый oversized hit → рассмотрение следующего, final mutation → отсутствие packet.
Добавить counterexample first-fit против более выгодной комбинации. Он **не баг
новой policy**, но его потеря должна попасть в отчёт. Не писать `optimal_in_inventory`.

## 7. Checks и diagnostic replay: что разрешено сравнить

Основной strict run использует существующие hard checks и unchanged
`read_context_admission()` над **actual предложенным window**, не search passage
вне него. Предварительно `source_window_eligibility()` и structural policy O/P.
Если непроверенная condition — unknown, не permission. Не заимствовать hard subject
или condition из другого окна/owner; incoming approval/proof flags игнорировать.

Новый code только orchestrates existing checks; не расширять relation grammar.
Known fact не должен сертифицировать private sibling. Если legacy control не
распознаёт такой read window, записать refusal, не добавлять rescue.

После strict sweep выполнить **один** counterfactual replay при 3000:
тот же inventory и serializer, снять только `no_local_topic_witness` refusal.

```python
def read_reason(item, *, question, identity, diagnostic_topic_relaxed=False):
    source = source_window_eligibility(
        item, question=question, expected_project_identity=identity)
    if not source.eligible:
        return source.reason
    from docmancer.docs.domain.query_terms import query_constraint_roles
    from docmancer.docs.domain.evidence_qualification import _visible_term_present
    roles = query_constraint_roles(question)
    if any(not _visible_term_present(term, item['snippet'], exact=True)
           for term in (*roles.hard_exact, *roles.bound_subjects)):
        return 'missing_exact_or_subject'
    result = read_context_admission(
        item, question=question, expected_project_identity=identity)
    if result.allowed:
        return None
    if diagnostic_topic_relaxed and result.reason == 'no_local_topic_witness':
        return None
    return result.reason
```

Structural/owner checks вызываются отдельно **до** `read_reason` и снова на final.
Adapter callbacks нового selector (это новый research код, не existing API):

```python
def select_case(proposals, *, question, identity, query_plan, budget,
                structural_reason, diagnostic_topic_relaxed=False):
    def check(proposal):
        reason = structural_reason(proposal)
        if reason is not None:
            return reason
        return read_reason(proposal['item'], question=question, identity=identity,
                           diagnostic_topic_relaxed=diagnostic_topic_relaxed)

    def build(packet):
        return render_packet([p['item'] for p in packet], query_plan=query_plan)

    return ordered_packet(proposals, budget=budget, check=check, build=build)
```

`structural_reason` реализовать ровно по P/O из шага 4: проверка исходного owner,
intact atoms, authorized extent и unsupported structures; не строковый semantic
detector. Для O structured window должен равняться whole-owner span из snapshot.
Другие reasons не разрешать: ни source, ни hard constraints, ни typed/condition
refusals. Это не «safe BM25 admission accepted». Replay metadata пометить
`diagnostic_only=true`, `eligible_for_rollout=false`. Не публиковать его через MCP.
Любой echo/scattered/wrong-relation negative, получивший sources, считать
**false admission**, даже если snapshot validator прошёл.

Снимать другие checks или подбирать topic threshold после этого replay запрещено.

## 8. Обязательные cases и что assert/log

| Case | Обязательная проверка |
|---|---|
| B1: intro + fence + following restriction | O либо содержит всё, либо abstains; command-only запрещён |
| B1 около 2048-byte passage boundary | P показывает отдельный restriction; O не теряет его при fit |
| B1 с длинным ordinary background | O может не поместиться даже в 3000; явно `dto_budget`, без clipping |
| Restriction под следующим heading/owner | Не объявлять semantic closure по section; потерю показать как unresolved/unsafe, не PASS |
| Intact/clipped list/table/code | O сохраняет header/key/intro/items; clipped proposals отказ |
| Standalone ordinary prose | Не требует whole parent из-за чужого примера дальше в разделе |
| B2 inventory 15/30 | First-fit завершён, packet nonempty при verified feasible rows; visits ≤30 |
| `mkdocs-05` | Literal required rule в final DTO; не только retrieval hit |
| `httpx-07`, `pydantic-07`, `ruff-07` | Known claim отдельно visible; private tail unresolved; false support/edit |
| Heading/link/question echo/scattered/reordered | Strict negative packet empty; diagnostic leakage отдельно |
| Factual positive и negative answer | Read не превращается в proof противоположной claim |
| Wrong source/project/path/version/scope/freshness/risk/request/hash/span | Ни один budget/replay не допускает |
| Wrong subject/literal/condition, lost negation/exception | Отказ; большой соседний текст не выдаётся за подтверждение |

Для B1 tests label restriction допустим только в assertion/evaluator, никогда
в алгоритме. Cross-owner test не решать чтением oracle или special phrase.
Сохранить старые B1/B2 Reds; новые tests проверяют **другой** контракт.

## 9. Runner: только шесть strict cells и один diagnostic replay

Сделать CLI нового `grounded_budget_probe.py`:

```text
--output PATH                       новый output directory, не перезаписывать
--budgets 800 1500 3000              только эти значения
--policies passage owner            P/O; один cached retrieval на case
--diagnostic-topic-replay             только owner policy при budget=3000
```

1. Сначала synthetic cases из шага 8 и четыре frozen cases.
2. Затем **все cases** `eval/evidence_quality_v2/cases.json`: без исключения
   `partial`/`unsupported`/negative. Не менять старые answerability labels под 3000.
3. `assess_context(case, payload, registry_for(...))` вызывается только **после**
   selection. При `payload=None` evaluator получает `{'sources': []}` как отсутствие
   evidence, не successful DTO. `needs_review` не PASS.
4. Baseline real native route снять на тех же corpus bytes/request paths при 800
   existing observer/service. При 1500/3000 legacy не выдавать за изменённый native
   route: сравнивать research policy с самой собой, меняя только budget.
5. Все checks/operational errors сохранить. Не заменять отказы «нулевым качеством»
   и не исключать их из общего знаменателя. Baseline precedence/vector failures
   перечислять отдельно, не исправлять в этом эксперименте.

На каждый case/policy/budget сохранить:

```text
request, corpus/source/generation/profile IDs
native ranks, retrieved/proposed/final spans, omission reasons
hydrated passage bytes, unique raw snapshot bytes, proposal bytes, metadata bytes
DTO admission units, canonical bytes, body-only units, envelope overhead
source row count, visits/check_calls/build_calls, elapsed_seconds
known claims visible/lost, private tail unresolved, semantic needs_review
source/guard validation errors, relevance false admission/abstention
answer_supported, answer_available, edit_ready
```

Логи — структурный JSON/JSONL, не весь raw_document в stdout:

```python
import json
import sys


def trace_event(enabled, **fields):
    if enabled:
        print(json.dumps(fields, ensure_ascii=False, sort_keys=True), file=sys.stderr)
```

Временные prints разрешены только в research runner или по `--trace`; после
диагностики удалить ad-hoc prints, оставить saved artifacts и opt-in trace.

### Команды исполнителя

Исполнять из проекта. Приведённый probe CLI **нужно сначала реализовать**, он
не существует на момент составления плана. Новые tests зарегистрировать по
`tests/diagnostic_labels.py`: hash sorted de-parameterized node IDs, label behavioral
для реально исполняемых проверок; label не означает production acceptance.

```bash
PYTHON=/usr/bin/python3.12
"$PYTHON" -c 'import sys, pytest, docmancer; print(sys.executable, docmancer.__file__)'
mkdir -p "$HOME/.cache/docatlas-experiments"
RUN_DIR=$(mktemp -d "$HOME/.cache/docatlas-experiments/grounded-budget.XXXXXXXX")
export PYTHON RUN_DIR
"$PYTHON" -m pytest -q tests/docs/test_grounded_budget_probe.py
PYTHONPATH=. "$PYTHON" v2plan/grounded_budget_probe.py --output "$RUN_DIR/probe" --budgets 800 1500 3000 --policies passage owner --diagnostic-topic-replay
"$PYTHON" -m pytest -q tests/docs/test_source_window_eligibility.py tests/test_retrieval_passages.py tests/test_retrieval_passage_index.py tests/test_lexical_passage_retrieval.py
"$PYTHON" -m pytest -q tests/docs/test_read_context_admission_boundary.py tests/docs/test_context_constraint_roles.py tests/docs/test_source_bound_subject_context.py tests/docs/test_shared_context_proposals.py
"$PYTHON" -m pytest -q tests/docs/test_gate_a_review_blockers.py
git diff --check
```

Если interpreter не имеет dependencies — показать infrastructure blocker; не
устанавливать модели и не считать import error behavioral Red. Сохранить stdout,
stderr и exit каждого run в новом `RUN_DIR`; исторический Gate A run ожидаемо Red.
Никаких git reset/checkout/auto-stash, push/merge или создания нового worktree.

## 10. Решение по результатам — без очередного tuning цикла

Составить таблицу, **с реальными числами**, P/O × 800/1500/3000:
known-claim delivery, lost baseline partial claims (IDs), false admissions,
unsafe restriction loss, `needs_review`, actual DTO units p50/p95/max,
latency p50/p95, raw/proposal bytes, guard/operational errors.

| Наблюдение | Решение |
|---|---|
| Strict O проходит B1/negatives и сохраняет обязательные baseline facts при 800 | Budget не причина; продолжить isolated integration простого selector |
| То же проходит только при 1500 или 3000 | Жертвовать компактностью; рекомендовать минимальный **проверенный** budget; production budget пока не менять |
| При 3000 O теряет context только потому, что owner больше budget | Простая whole-owner policy ограничена размером; назвать unsupported формы, не новый shrink rescue |
| P теряет restriction, O сохраняет | Passage boundary недостаточна; не выпускать P как completeness-preserving route |
| Strict отказывает при всех budgets, diagnostic topic replay возвращает факты | Блокер relevance policy, не размер; показать также все новые false admissions |
| Replay сохраняет facts, но допускает negatives | Более слабый read-контракт имеет измеренную цену; не принимать его без отдельного продуктового решения |
| Candidate pool не содержит witness | Discovery/resource loss; не обещать исправление за счёт final budget |
| Зависимость пересекает owner/не наблюдается структурно | Arbitrary-doc completeness не установлена; требуются declared source units или отказ от такого обещания |
| First-fit теряет обязательный факт, который feasible в другой комбинации | Отказаться от этой selection policy; не возвращать brute-force/greedy tuning автоматически |
| Любой source/security/condition/span guard bypass | Отклонить вариант независимо от recall/budget |

**Минимально приемлемый strict вариант:** zero new guard/negative failures;
zero lost обязательных previously delivered known claims; B1 restriction retained
при admission; DTO ≤своего budget, ≤3 rows; no proof/edit credits. Cross-owner
неизвестности исключают обещание универсальной полноты даже при локальном Green.

Если ни один strict вариант не удовлетворяет этим условиям — итог не «ничего
не понимаем», а перечень подтверждённых цен: budget, bounded structural scope,
relevance precision или selection retention. Не ослаблять tests ради решения.
Остановить replacement в этом виде; сохранить 01–04 и действующий route.

После отчёта **остановиться**. Не запускать новую сетку sizes/weights/windows.
Full paired regression, installed MCP, независимый held-out/reader gate и rollout
— только после выбора конкретного проверенного контракта. Этот эксперимент их
не заменяет и не делает production step 05 Green.
