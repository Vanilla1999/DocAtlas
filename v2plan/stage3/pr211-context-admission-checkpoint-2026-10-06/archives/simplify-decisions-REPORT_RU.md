# PR211: семантические обязанности решений A/B

2026-10-06. Ветка `diagnostic/pr211-simplify-decisions-20261006`, baseline
`37bfd0668f819935dd9e027bd9d8bf767fcd185a`.

**Вывод: безопасное малое семантическое упрощение A/B на существующих verdicts не
доказано. Продуктовый кандидат не предлагается.** Структуры уже разделяют source
eligibility, context, proof и attribution; некоторые потребители снова сводят их
к boolean. Простое удаление proof-проверок теряет no-value границу, а распространение
их отрицательного результата на context теряет полезные неизвестные detector факты.
Это не доказательство невозможности любого будущего малого изменения.

Прочитаны primary `v2plan/stage3/PR211_POST_PARALLEL_REASSESSMENT_RU.md` и
`PR211_RED_ANALYSIS_REVIEW_RU.md` в `/tmp/opencode/docatlas-stage3-integration-active`,
а также `/tmp/opencode/pr211-parallel-review/REPORT_RU.md` (далее **reviewer**).
Ниже пути к коду/документации относительны этому worktree; `app/` означает
`docmancer/docs/application/`, `domain/` — `docmancer/docs/domain/`.

## 1. Краткая таблица решений

| Решение | Существующий владелец/представление | Что положительный результат разрешает | Что отрицательный НЕ доказывает |
|---|---|---|---|
| Допустимость источника | `evidence_policy_rejection_reason`; reference/source/scope/span validation | Рассматривать текущие разрешённые bytes данного источника | Ничего о наличии факта в других источниках; сам допуск ещё не релевантность |
| Релевантность read-context | `EvidenceQualification`, `ContextDisposition(retrieval_only)` | Бounded цитату по запросу при соблюдении policy | Отсутствие detector witness не равно отсутствию полезного контекста |
| Поддержка утверждения | `ProofObligation`, local proof, source-bound assignments | Засчитать ровно связанный subject/relation/value/condition witness | `None`/`valid=false` означает «не подтверждено этим detector», не «факт отсутствует» |
| Публичная attribution | `ContextSelectionDecision`, `attributable_query_ids`, final requalification | `covered_query_ids` для видимых проверенных направлений | Missing query не запрещает всякий partial context; covered query не доказывает полноту ответа |
| Отбор дополнения | new components/query directions, authority, same-origin footprint | Потратить ограниченный бюджет на признанный прирост | Нет нового распознанного component/query ID ≠ семантический дубликат |

Опорные реализации: `domain/evidence_qualification.py:202–239,271–301`;
`app/need_context_disposition.py:95–182`; `app/need_context_projection.py:83–108`;
`app/context_selection.py:33–74,112–166,180–224,255–277`.
Source bytes/identity/conditions проверяются отдельно: разрешение источника не
выводится из его authority или lexical overlap.

### Контракт документации

- Принятый **ADR 0003** (`docs/adr/0003-context-first-project-reads.md:9–15,24–45`):
  project/module reads — `docs_context`; полезный partial context допустим;
  host lookups улучшают recall, но не дают proof; coverage пересчитывается по видимым bytes.
- `docs/modules/question-planning.md:11–13,31–35,48–50`: fail-closed QuestionPlan
  относится к certification, read-only retrieval не требует supported QuestionPlan;
  evidence selection не вправе подменять исходные обязательства.
- `docs/mcp-docs-server.md:42–47` и `docs/mcp-response-contract.md:7,18–21,43`:
  read-context остаётся cite-only с false answer/edit flags; отсутствие безопасного
  контекста означает abstention, retrieval coverage не является support verdict.
- ADR 0002 **superseded**: нельзя использовать его разрешение upgrade project reads
  до `docs_answer` как текущую норму. Наличие useful numeric context также не означает
  необходимости server answer certification.

Документы не дают универсального критерия «полезен ли delegation-only текст для
прямого вопроса о числе». Frozen case даёт конкретный отрицательный gold:
`eval/agent_developer_v2/cases.json:111–131`; local proof tests требуют число,
но проверяют именно proof, не весь read admission
(`tests/docs/test_quantified_attribute_scope_isolation.py:27–38`).
Из общих context-first формулировок не следует право отменить этот gold.

## 2. Где boolean превращает «не распознано» в отказ/дубликат

| Место | Текущая проверка | Семантическая подмена/ограничение |
|---|---|---|
| `app/_docs_context_projection_core.py:89–94,245–250` | `strict_single_attribute and not component_ids` → `missing_attribute` | Полный **разбор вопроса** плюс не найденный witness превращаются в veto чтения всего source. Нет исключения для явно заданного lookup; value_kind любой truthy, не только number |
| Там же `:251–284,543–545` | Нет qualified direction и component → discard; дополнительные path/contract filters | Operational admission floor; «не прошёл квалификацию» нельзя описывать как доказанную нерелевантность. Path-only guard защищает от пустой навигации, его снятие не обосновано |
| Там же `:385–391,553–572` | authority + complete scope + `not new_components` + отсутствие независимого public/canonical/same-origin gain → `authority_duplicate` | Совпавшее направление и отсутствие нового распознанного proof трактуются как избыточность supporting. Полнота parser не доказывает полноту уже выбранного документа |
| Там же `:573–610` | Нет новой direction/gain → `no_new_direction`; недостаточно новых host terms → отказ | Учёт разнообразия в бюджете, не entailment и не общая проверка семантического дублирования |
| `domain/admission_contract.py:34–42,65–80` | witness `absent` → `admitted=false`; `unknown` → legacy qualifier | `absent` получается из false локального matcher, не из доказательства отрицания факта. Три состояния уже есть, но их названия не устраняют false negatives |
| `app/retrieval_need_support.py:82–114,127–133` | `proof is False` снимает qualification, `None` не снимает | Ещё один существующий semantic veto на retrieval need. Его blanket removal не доказан безопасным |

У B есть дополнительная статическая тонкость: `selected_authoritative_public_ids`
строится через **qualified**, а не **attributable** IDs и проверяется на непустоту,
не на доказанное покрытие конкретного дополнительного факта. Admission-only trace
тоже может участвовать в этом внутреннем сигнале authority. Это чтение условия,
не новый нативно воспроизведённый B-failure и не доказательство публичной утечки.

Сама пустота `component_witnesses` объединяет policy rejection и отсутствие local
proof (`context_selection.py:39–50,61–74`). Нельзя использовать её как универсальный
новый eligibility verdict или переносить старое решение между изменившимися windows.

## 3. A: собственная нативная проверка и граница упрощения

`decision_probe.py` запускает native ingestion/public call через существующую fixture;
decision functions, dispatcher и выдача не подменены. Fixture наблюдает projection,
проверяет финальные snippet/line range, snapshot validation, false authority flags и
лимиты 800 tokens / 3 sources. Отдельный unit вызов `component_witnesses` помечен в JSON
как unit probe. Все случаи ниже — синтетический **project** scope, не повтор frozen module case.

Вопрос: `How many retry attempts does ProjectRetryPolicy allow?`.
Во всех шести capture план complete, один attribute `retry attempts / number`.

| Текст | Unit component witness | Native baseline / путь | Public coverage |
|---|---:|---|---|
| `OrderSubmission ... delegates network retry decisions to ProjectRetryPolicy.` | нет | `ok`, missing_attribute → fallback | original missing |
| `ProjectRetryPolicy allows at most two retry attempts.` | да | `ok`, основной путь | original covered |
| `ProjectRetryPolicy retry policy allows at most two attempts.` | нет | `ok`, missing_attribute → fallback | original missing |
| Heading `ProjectRetryPolicy` + `The retry policy allows at most two attempts.` | нет | `ok`, missing_attribute → fallback | original missing |
| `ProjectRetryPolicy delegates retry decisions to OtherWorker, which allows nine retry attempts.` | да | `ok`, основной путь | original covered, **не answer support** |
| Delegation + `The diagnostic command is inspect-retries`, с явным command lookup | нет | `ok`, missing_attribute → fallback, команда доставлена | original **и lookup missing** |

Везде `answer_supported=answer_available=edit_ready=false`. `covered_query_ids`
не превращает nine в разрешённый ответ о ProjectRetryPolicy. Про отсутствие ложных
утверждений downstream host эта проверка ничего не устанавливает.

**Контрпримеры в обе стороны:**

- Ужесточение A (veto fallback по strict) действительно теряет полезное `two attempts`:
  native baseline/candidate пары уже доказаны reviewer:214–247. Здесь независимо
  подтверждены baseline доставка и одинаковый отрицательный detector verdict.
- Ослабление/замена veto на `ContextDisposition.state != blocked` не различает
  no-value delegation и полезную числовую перефразировку: в наших traces оба получают
  `retrieval_only/current_topic_without_complete_proof`. Это препятствие reuse, а не
  запуск нового candidate. No-value поведение нельзя объявить корректным только из-за false flags.
- Просто требовать существующий number score тоже недостаточно: co-occurrence чужого
  числа уже проходит более сильную component-проверку. Код ordinary attribute:
  `domain/_answer_units_part02.py:543–546`; literal attribute recognition `:32–52`,
  number recognition `:188–198`. Разница split/heading не сводится к heading inheritance.

`ContextDisposition(supported)` не является универсальной заменой: он ограничен
typed scalar needs (`need_context_disposition.py:160–175`), числовой запрос здесь
компилируется unresolved/unknown, а `retrieval_only` шире нужной strict границы
(`domain/need_contracts.py:63–78`). Единый выбор этого verdict ничего не докажет о числе.

## 4. B: authority — приоритет, не доказательство избыточности

Native B-пары **в этой работе не запускались**. Reviewer:24–59 независимо подтвердил:
на неполном плане снятие `component_scope_complete` из authority_duplicate убирает
исходный distractor и добавленную строку `A changed hash produces a red warning.`.
Потеря последней — потеря текста, не доказанная потеря обязательного ответа.
Исходный тест действительно включает notes в scope manifest
(`tests/test_docs_service_part03.py:10–15,52–73,80–104`): это не чужой corpus.

**Обе стороны ошибки:**

- Сохранение только lexical/query novelty допускает note, прямо не определяющий
  запрошенный acceptance contract. Это подтверждённый baseline distractor.
- Признать любой supporting без новых components дубликатом нельзя. Например,
  дополнение «For Phase 2.3, a SupportDecision with a changed decision_hash is rejected
  before presentation» непосредственно относится к исходному exact-contract вопросу
  и может добавлять недостающую норму. Это **гипотетическая acceptance-пара**, не
  подтверждённый native counterexample: нужны согласование смысла и проверка порядка,
  неполноты плана, visible quote и реального authority_duplicate на обеих версиях.

Новое query ID означает новое направление поиска, не обязательно новый факт; старое
ID не исключает нового факта. `same_origin_gain` защищает видимое дополнение **того же**
origin (`app/context_variant_retention.py:19–27`), но не решает междокументную полезность.
`VariantFootprint` описывает уже qualified bytes, не новый semantic oracle
(`app/qualified_support_units.py:1–4,35–42`). Их reuse полезен для retention, но не
обосновывает отбрасывание всех lower-authority источников при incomplete parsing.

## 5. Конкретное remove/reuse заключение

**Не переносить A/B и не удалять proof-проверки как «лишние». Ноль предлагаемых
продуктовых designs в этом отчёте.** Проверенный смысл возможного упрощения — убрать
negative proof как универсальный read/dedup verdict и переиспользовать существующие
qualification/disposition/attribution — пока не имеет безопасного критерия различения.

- **A:** удалить `strict_single_attribute` veto и оставить retrieval qualification
  недостаточно обоснованно; добавить его на late fallback — опровергнуто numeric
  positive. Reuse `retrieval_only` пропускает no-value, reuse component/typed support
  теряет полезный unknown. Нет принятого remove/reuse patch.
- **B:** удалить только scope guard нельзя считать упрощением без изменения политики:
  это расширение отрицательного verdict на unknown. Удалить весь authority_duplicate
  и положиться на следующий `no_new_direction` не является ремонтом известного случая:
  incomplete baseline уже обходит authority_duplicate, но distractor проходит дальше.
  Same-origin retention не заменяет cross-source relevance. Нет принятого remove/reuse patch.
- **Переиспользовать по назначению:** eligibility checks для допуска source;
  component/local proofs и `visible_assignments` для положительной поддержки и её
  сохранения; qualified directions для admission; attributable IDs для public coverage;
  source-local footprints для retention. Не давать этим понятиям дополнительные
  полномочия через новое имя общего boolean.

Attribution-boundary сохраняется независимо от A/B: `context_selection.py:267–276`
исключает admission-only; `evidence_qualification.py:520–539` даёт parent attribution
только audited rewrite; `_docs_context_projection_core.py:868–937` requalifies visible
bytes; `_docs_context_payload.py:44–64,113–138` отдельно считает facets и false flags.
Поздний fallback намеренно очищает query matches (`need_context_projection.py:148–150`).
Удалять эти проверки под лозунгом «context не proof» небезопасно. Общий crop/merge audit
здесь не проводился; ограничения reviewer:61–103 остаются.

## 6. Решения владельца и минимальная приёмка

**Product/contract owner, не автор boolean refactor, должен зафиксировать:**

1. Для прямого numeric вопроса: порог useful context при отсутствии распознанного числа.
   До согласования сохраняется frozen no-value abstention и требование не терять
   реальный `two attempts`; согласованная потеря recall была бы изменением политики.
2. Для того же вопроса с **явным независимым lookup**: может ли полезная command quote
   дать partial docs_context при missing numeric original? ADR 0003 поддерживает
   additive read-only recall, но strict veto сейчас действует до учёта host_ids.
   Lookup не может создать numeric obligation/proof или покрыть original автоматически.
   Наш command capture доставлен с missing lookup; это не доказательство исправной
   независимой lookup qualification. Нужна явная ожидаемая quote + coverage политика.
3. Для B: authoritative-first является предпочтением либо правилом исключения
   supporting? Допустим ли same-query релевантный новый факт при incomplete plan?
   «Source_of_truth существует» не отвечает на вопрос о полноте документа.
4. Что host вправе утверждать по unrecognized context: ADR 0003 поручает ему synthesis,
   а `mcp-docs-server.md:42` ограничивает ответ covered claims. Сохранение useful quote
   не должно молча расширять поддержку facets. Это уточнение контракта, не status switch.

Domain owner сохраняет ownership вопроса и local proof; application owner — bounded
delivery и visible requalification (`docs/modules/question-planning.md:15–21,31–35`).
Owner policy не подменяет проверку native поведения.

Минимум перед любым реальным candidate: заранее согласованные пары no-value/свой
numeric/чужой numeric, exact/split attribute и inline/heading; strict запрос с/без
explicit lookup; useful unknown; для B — request-relevant supporting/distractor при
**одинаковом authoritative-first порядке и incomplete plan**. Проверять final quote,
источник, original/lookup coverage, false flags, сохранение доказанных witnesses,
policy negatives и прежние budgets. Если трогается весь strict predicate — другие
value_kind тоже входят в scope. Затем paired native baseline/diff и независимое review;
full CI имеет смысл после принятого изменения, не вместо semantic acceptance.

## 7. Артефакты и предел доказательства

Команда из этого worktree (exit 0, шесть captures, это diagnostic, не новый acceptance gate):

```sh
DOCATLAS_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /home/viadmin/StudioProjects/hermes/docmancer/.venv/bin/python decision_probe.py > decision_probe.log 2>&1
```

Полные исходные/public packets, планы и traces: `decision_probe.json`; краткая таблица:
`decision_probe.log`. Hash production projector:
`3fabbd99b47bb964d253dea96f7ada5d88001e554d1426d4873ee8cfa683103d` — baseline reviewer совпадает.
Не запускались candidate A/B, full CI, holdout или downstream answer evaluation.
Native наблюдения шести синтетических случаев не оценивают частоту дефектов.
Созданы только этот отчёт и собственные диагностические script/log/JSON; product,
существующие tests/manifest и другие worktrees не изменены. Commit/push/merge нет.
Финальные `git diff --exit-code` и `git diff --check` — exit 0; status содержит только
четыре перечисленных untracked артефакта. Read-only JSON audit подтвердил шесть strict
планов и false public authority flags.
