# A: предлагаемый admission contract V3 — только узкие scalar-label candidates

Дата: 2026-10-12. Статус: **предложение координатору, НЕ зафиксированный контракт и НЕ разрешение product edits**. Владение A: только этот файл. Runtime/models/host/tests/compile/AST не запускались; V2/questions/oracle не изменены. Прежние шесть изменённых/untracked product/eval файлов сохранены.

## 1. Реальный public путь и границы доверия

Прочитаны repo `AGENTS.md`, V2 `COMPACT_CHECKPOINT_RU.md`, `UPSTREAM_BLOCKER_RU.md`, `PROTOCOL_V2_RU.md`; дополнительно raw public HOLD03/HOLD05, frozen corpus и существующая public negative family.

1. `docmancer/docs/interfaces/mcp/context_tools.py:289–339`: `handle_context_tool` под `original_body_read_scope` вызывает настоящий `app.get_docs_context`. Network/bootstrap/refresh выключены handler-ом; после результата действуют operational veto и model-visible validation. Scope живёт до окончания синхронного handler, включая projection.
2. `docmancer/docs/domain/original_body_discovery.py:33–79`: host env opt-in фиксируется один раз на вызов. Только absolute local project/original question, без library/module/maintenance/patch format/explicit lookup. Caller wire/candidate не может включить режим или создать receipt. ContextVar не sandbox против произвольного Python.
3. `docmancer/docs/application/_project_docs_service_part03.py:223–284`: реальное retrieval, `reference_context.prepare`, application-owned discovery receipt; original и второй authoritative read (возможен page expansion). V3 не должен переписывать acquisition.
4. `docmancer/docs/application/reference_query_tagging.py:36–68,98–113`: receipt сверяется с application-owned finite reference context; canonical qualification вызывается до fallback admission.
5. `docmancer/docs/domain/literal_context_admission.py:261–300,368–391`: fresh root/catalog/member/source/window checks через canonical qualifier; fallback только при `insufficient_visible_match`, не при source-policy отказе. Для ordinary/B1 fallback обязательны отсутствие canonical missing exact terms и проверенный raw body window. Admission сохраняет failed original qualification и `coverage_credit=False`.
6. `docmancer/docs/domain/ordinary_body_context.py:208–239`: live native binding; проверенный structural owner; unresolved-name constraint; затем **все digit-bearing literal terms вопроса в одном body block**. В ordinary lane далее требуется phrase/technical witness; B1 заменяет только topical witness на substantive body + `relevance_unassessed=True`.
7. `part03:328–418`: cross qualification, ordering, optional existing-object selector, packing/retention. `project_doc_ranking.py:195–225` и `_docs_context_projection_core.py:258–303` **повторно** вызывают тот же admission на actual bytes; downstream selector не может восстановить исключённый upstream pool.

Различать четыре вещи:

| Условие | Что доказывает / чего не доказывает |
|---|---|
| Project/catalog/member/generation/hash/window, source class, lifecycle, native receipt, access/consent/final validation | Допустимость чтения и подлинность источника; не relevance и не ответ |
| `prepared_owner_rejection` | Подлинность текущего structural owner и containment окна; не семантическую принадлежность API |
| Unresolved-name presence + hard exact | Лексическая identity/query boundary; не access grant и не полноту отношения |
| Same-block query numeric literals | Консервативный query-condition admission veto; не сравнение величин и не numeric entailment |

**Не называть снятие query-number equality исправлением source-policy.** Source policy не меняется. Не путать retrieval lexical `candidate_lexical_match.exact_terms` с canonical `observed_qualification.missing_exact_terms`.

## 2. Raw V2 числовой вопрос (без нового исполнения)

`admission-selection-v2/public/HOLD03_B1.json:5`:

> Мастер получил одинаковую массу сосуда при двух взвешиваниях через 12 часов. После обжига неглазурованной партии температура 100 градусов. Что эти наблюдения разрешают в отношении просыхания, дверцы и выгрузки, и чем отличается правило дверцы для глазурованной партии?

Raw: `insufficient_evidence`, context/answer/edit=false, ranking/projection not reached; десять candidate records. Для loading виден свежий source reference `[21,335)`, generation/project/hash/catalog, canonical missing_exact_terms=[] и admission=null (`:230–330`). Это observed payload, **не observed numeric branch receipt**.

Frozen `review/corpus.json:12–13`: loading даёт равную массу через **12 часов**; cooling содержит пределы **80/120/40 градусов**, не 100. Вопрос ставит условие 100, а не требует цитату с числом 100. Все `{12,100}` в каждом body block — достаточный реконструированный numeric veto, но более ранние причины не исключены. Независимые исходные правила позволяют сравнения 100≤120, 100>80, 100>40; admission сам их не вычисляет и не сертифицирует.

HOLD05 raw question (`public/HOLD05_B1.json:5`) содержит **1,3 метра**; sailing source — **1,4 метра**, refunds — вообще без цифр. Старый `_literal_terms` разбивает запятую: query numeric set `{1,3}`, source `{1,4}`. Это не единый decimal identity check. Нельзя чинить split так, чтобы считать совпадающую `1` достаточным числовым доказательством.

HOLD06 cargo не повторяет 1,4; его отсутствие у selector — отдельная multi-document contribution задача. Она не решается лишь scalar comparison admission.

## 3. Предлагаемый минимальный opt-in delta

Предлагаемое новое значение **`DOCATLAS_EXPERIMENT_ADMISSION=scalar_label_candidates_v3`**, default OFF. Старое `policy_candidates_v1` и ordinary/default должны оставаться точными прежними ветками. Новый режим наследует B1 **unassessed candidate semantics**, не обещание автоматически восстановить strict empty-source contract B0.

### Правило (конкретное, без словаря единиц/benchmark IDs)

Сначала выполнить все прежние canonical source/window/hard-exact/native-receipt/owner/unresolved-name checks. Сначала также оставить существующий B1 same-block numeric route; менять только fallback при его numeric veto в **новом** режиме.

Дополнительный кандидат разрешён только если одновременно:

1. В original question есть цифры, и **каждый** digit-bearing lexical token относится к полностью source-coordinate-bound конструкции `scalar whitespace label`. Scalar — целиком самостоятельное беззнаковое десятичное число `digits` либо `digits[.,]digits`; label — следующее самостоятельное буквенное слово. Decimal comma атомарна. Никакие части диапазона, версии, composed identifier, namespace/path, exponent, знакового/операторного выражения или более длинного technical token нельзя считать scalar. Не маскировать неподходящие digit-bearing tokens: при хотя бы одном таком токене весь новый fallback закрыт.
2. В одном существующем masked structural **body block** найден хотя бы один полностью самостоятельный source `scalar whitespace label` с **тем же whole-word label** из original question (casefold как в существующих lexical witnesses). Source scalar может отличаться от query scalar. Обе числовые конструкции должны быть в body/исходном вопросе, а не в heading/path/table header/link. Не допускается заимствование числа и label из разных rows/list items/blocks.
3. Block substantive и source-bound, как B1; вернуть exact raw source coordinates, private native binding, query/source pair spans и `relevance_unassessed=True`, отдельный kind, например `scalar_label_original_candidate_v3`. `numeric_condition_unassessed=True`: **совпадение label не доказывает, что это единица или одно и то же условие**. Это синтаксический scalar-label candidate, не semantic measurement parser.

Только одна local пара нужна для candidate: loading не обязан повторять temperature; cooling не обязан повторять интервал взвешивания. Но nonnumeric block не получает исключения. Никакого скрытого pairwise/Cartesian объединения всех кандидатов и никакой расширенной доставки по folder/group ID.

Source numbers/labels/text не меняются; исходный question не переписывается, не удаляются цифры ради qualification. Не считать threshold равным request value, не выводить >/< из лексики, не вычислять coverage/answer_supported из нового witness. Host получает прежний public raw snippet, а не oracle/pair interpretation. Ranking scores не создают source/answer authority.

**Почему это уже, чем снять numeric guard:** есть новый host-only режим; все non-scalar числовые requests продолжают прежний veto; нужен настоящий body scalar с общим literal label, а не любой source digit; owner/identity/hard exact не ослабляются; default и V2 не меняются. Это кандидатное условие, не гарантированное relevance решение.

Статическое ожидание, НЕ PASS: loading `12 часов` и cooling `80/120/40 градусов` смогут стать scalar-label candidates для HOLD03; sailing `1,4 метра` — для HOLD05. Получится ли полная final public выдача, зависит также от остальных guards/packing. Исполнение должно проверять actual final bytes и source boundaries, не только witness.

## 4. Сохранённые negative требования и empty-source конфликт

Безусловно сохраняются: чужие project/module/library/scope/version, stale generation, изменённый raw/hash/catalog/member/window, malformed structural owner, missing hard-exact, replay/forged serialized receipt, explicit lookups, отсутствие настоящего body, network/bootstrap/write, answer/edit authority. Не расширять unresolved-name guard; HumanEval/LeetCode vs HumanEval — вне V3. Не объявлять все ACL/consent/version состояния проверенными по чтению кода.

Существующая integration family `tests/test_project_context_quality_v2_protocol.py:466–629`:

- `How are packets delivered with priority 7.` и `... priority 7-9 during concurrent recovery?` должны оставаться empty с false authority. Источник `Packets are delivered after each request.` не содержит body scalar-label; `7-9` не scalar; у `7.` нет следующего label. Не признавать слово `during` числовой единицей и не отрезать диапазон до 7.
- OtherAPI не должен получать packet relation/answer authority от DeliveryEngine. Composed tokens не должны распадаться; Setext/link/table headings не должны давать body witness. Unrelated sources не должны давать supported affirmative answer.
- **Для режима V3, наследующего B1, это не универсальная гарантия `sources=[]` для всех semantic negatives.** B1 уже имеет зафиксированные nonempty failures OtherAPI/compound/Setext/unrelated. Новый scalar-label fallback тоже может доставить неподходящий body с тем же буквальным label. Honest refusal и false answer flags не делают прежний empty-source oracle PASS.

Координатор обязан явно выбрать contract axis: разрешён ли opt-in **unassessed retrieval-only** context при неустановленной relevance. Никакой перезаписи V2 oracle: старые strict negatives остаются CURRENT_CONTRACT FAIL, если источники непусты. Если обязательны одновременно новый full numerical/multi-document recall **и** universal strict empty-source всех семантически неподходящих источников, **BLOCKER: безопасного узкого детерминированного правила на имеющихся receipts нет**. Нужен отдельный relevance/condition/relationship механизм и публичное доказательство; rank score не заменяет его.

Дополнительные обязательные будущие negative наблюдения: incidental scalar с тем же label не должен получать answer/coverage credit; unit-label другого показателя не должен считаться тем же условием; отсутствие local scalar-label оставляет fallback закрытым. Это требования к будущему integration+ протоколу, здесь проверок не добавлено/не исполнено.

## 5. Нерешённая multi-document граница / stop condition

Этот узкий контракт **намеренно не обещает** cargo HOLD06 или refunds HOLD05: в них нет body numeric-label pair. Нельзя допускать такие блоки просто потому, что где-то в project найден threshold. Catalog принадлежность/folder/family identity не доказывает тематическую связь; structural owner разных документов не общий semantic owner.

Возможный отдельный контракт потребует независимого source-bound contribution witness для каждого безчислового facet и live same-call связи с условием. В текущем общем admission API этой связи нет; admission повторно пересчитывается per-window в tagging/ranking/projection. Добавить глобальный «раз один fragment допустим, допустимы все» недопустимо. Dictionary-free ordinary phrase может доказывать лишь partial context, но не связь с numeric rule и не все HOLD05/HOLD06 связи. **Если цель V3 требует именно полного этих multifacet ответов, перед implementation нужен новый contract checkpoint; узкая scalar-label версия недостаточна.**

## 6. Минимальная назначаемая product поверхность после фиксации

Назначить одному implementer-у, пока ничего не изменять:

1. `docmancer/docs/domain/original_body_discovery.py`: capture точного нового env значения в существующем `_BodyRead`; отдельный live-mode predicate для scalar fallback. Existing policy-candidate predicate может признавать оба режима для общей B1 candidate machinery, но старое значение сохраняет старую numeric ветку. No wire option; mode immutable for invocation.
2. `docmancer/docs/domain/ordinary_body_context.py`: factor source/native/owner/unresolved eligibility из `_policy_valid_body_blocks` **без изменения default generator semantics**. Старый numeric filter оставить для ordinary/B1. Только experimental candidate function получает новый scalar-label fallback; чистый синтаксический парсер обязан хранить original spans, проверять maximal-token boundaries и не распадать `1,3`/`7-9`/IDs. Новый witness строится из original raw slice.
3. `docmancer/docs/domain/literal_context_admission.py`: максимум корректировка docstring о режимах/ограничениях; functional изменение не нужно, если generic ordinary kind/read-only witness путь принимает новый witness. Его canonical qualification/missing-exact/body-window checks не трогать.

Не назначать retrieval/service/qualification/query-rewrite/selector/ranking/projection/DTO validators для этого минимального delta. Они уже пересчитывают общий admission; существующий selector допускает только original qualified/admitted objects с live binding. Если реализация требует обхода downstream veto или нового global cross-candidate state ради PASS, остановиться и вернуть новый blocker, не расширять ownership молча.

## Решение для координатора

Можно фиксировать **только узкий scalar-label retrieval-only opt-in** с неизменным source policy/owner/hard exact, честным unassessed numeric/relevance и явно ограниченным recall. Full multi-document плюс сохранение всех strict empty-source negatives этим контрактом **не решены**. Product edits ожидают отдельной фиксации координатором; runtime budget здесь не использован.
