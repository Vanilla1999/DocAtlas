# Следующий эксперимент: explicit-reference own-body closure

**DESIGN ONLY — требует parent review.** Production/policy/данные не изменены;
симуляций, inference, downloads и новых model/threshold searches не было.
Предыдущий frozen Qwen experiment завершён validation FAIL. Его результаты
и все16 исходных cases сохраняются; теперь это seen development regression.

## Решение

Предлагаю **один** следующий эксперимент: conservative source-exact closure
явных fragment references из admitted evidence на **target own body**, его
ancestor introductions и используемые definitions. Не whole-root/subtree.

Target, добавленный по такой dependency, не обязан снова проходить unary query
threshold. Сохраняются два разных основания inclusion:

- `semantic_seed`: own body прошёл unchanged Qwen score>=tau;
- `explicit_reference_dependency`: существует поддерживаемая, однозначно
  разрешённая native reference edge из включённого evidence body.

Второе основание означает **консервативное сохранение связанного исходного текста**,
а не доказанную полезность ссылки или достаточность ответа. Стоимость любого
добавленного текста учитывается; экономия может не пройти gate. Порог остаётся
только правилом допуска seeds, не повторным фильтром явно связанной dependency.

Это устраняет конкретный *класс* потери: admitted statement с explicit ссылкой
больше не теряет разрешённый target own body из-за низкого unary score. Гарантия
условна: referring seed допущен, edge поддерживается parser, target однозначен,
source доступен/авторизован, scan/closure завершаются без emergency stop.
Гарантий recall неявных зависимостей, правильности seeds или child procedure нет.

## Сравнение двух альтернатив

| Вариант | Что решает | Новые предположения/цена |
|---|---|---|
| A. Explicit own-body reference closure | Не теряет разрешённый target body из-за второго threshold; source-exact, наблюдаемый граф | Все qualifying links принимаются консервативно, navigation noise и chains могут разрушить экономию |
| B. Query-aware relation selection `(query,referring body,edge,target)` | Потенциально отличает navigation от необходимой condition | Нужны relation-labelled data, отдельный проверенный механизм/criterion и calibration; ещё один learned false-negative boundary |

**Выбран A.** У текущего passage reranker нет установленного контракта или
независимого evidence, что его score оценивает необходимость directed relation.
Одна новая instruction, pair concatenation или тот же threshold на target не
создают такой механизм. B заслуживает отдельного исследования только при наличии
независимых relation obligations/negative navigation cases и приемлемого recall;
сейчас это больший, необоснованный diff. Объяснений «мыслей Qwen» не предлагаем.

## Точная proposed closure semantics

Новая structural recipe, например
`explicit_anchor_own_body_dependency_closure_v3` (имя согласовать до freeze).
Historical `minimal-structure-v1` и structural v2 остаются как есть.

### Множества и provenance

1. Scorer по-прежнему делает полный scan checked own bodies; exact query/prompt/
   target/full-containing-document/incoming context/tokenization/model pins
   не меняются. Ни closure result, ни labels не подмешиваются в model inputs.
2. Seed set S определяется frozen empirical threshold. Каждый S-body становится
   **expandable**. Собственные explicit fragment edges рассматриваются по syntax,
   не по query keywords/темам/heading names.
3. Для каждого однозначного разрешённого target добавляются target own body,
   heading и ancestor introductions; сам target становится expandable.
4. Механически добавленные ancestors **не становятся expandable только потому,
   что они ancestors**. Их incidental navigation links не запускают expansion.
   Если тот же body независимо входит в S или достигается dependency edge,
   его роль повышается до expandable и он обрабатывается ровно один раз.
5. Definitions, необходимые для интерпретации включённого текста (reference
   label/footnote), сохраняются целиком, с continuation lines и source-exact owner
   body. Definition resolution относится к исходному reference occurrence:
   `[x][ref]` → destination definition → target есть edge исходного body.
   Incidental links всего definition-owner body не становятся expanders.
   Nested explicitly used footnotes/definitions разрешаются до fixpoint; URL
   внутри необходимого footnote text считается его dependency. Эта разница
   требует учёта occurrence/definition span, не сканирования всех links owner
   как будто они нужны. Неподдержанная/неоднозначная syntax — явный gap.
6. Queue/fixpoint без малого cap/top-k. Dedup по полной source identity+parent
   span, не по одному path/anchor. Edge visited set предотвращает cycles;
   promotion auxiliary→expandable обрабатывается корректно. Порядок выдачи
   source-stable, исходный порядок секций внутри документа сохраняется.

Source identity: scope/project/module, version/generation, canonical source path,
native content/catalog hashes и offsets. Нельзя склеить одинаковые anchors из
разных версий. Новых discovery/fetch permissions closure не выдаёт. Existing
native qualification должна проверять каждый новый delivered span; graph строится
только из checked authorized sources текущего public acquisition и live recheck.
Repaired capability issuance/pricing/read-only semantics сохраняются без изменений.

### Navigation amplification и честные ограничения

- Link из selected overview/navigation body обрабатывается так же, как любой
  qualifying edge: target own body добавляется. Не объявляем overview noise по
  названию и не вводим скрытый topic/nav classifier. Если overview допущен ошибочно,
  риск amplification принимается и измеряется.
- Links только из auxiliary ancestors не расширяют graph. Это снижает incidental
  amplification, но может пропустить реально обязательную linked condition в
  ancestor intro. Такой случай должен присутствовать в holdout как obligation;
  при потере — FAIL, а не post-hoc promotion всех ancestors.
- Indirect chains A→B→C включаются, когда A expandable и B стал target dependency.
  Это не произвольная глубина1 и не quota. Cycles дедуплицируются; большой связный
  graph может приблизиться к целому корпусу. Тогда reduction FAIL или emergency
  stop, не truncation/ranking/capping для спасения результата.
- Anchor на heading-only parent: сохраняются header/ancestors, **дети автоматически
  не включаются**. Receipt получает `heading_only_target`/unresolved child coverage.
  Если для ответа нужны child conditions, они должны быть independently admitted
  или reachable explicit targets. Само наличие resolved anchor не доказывает
  полноту процедуры. Broad/nested obligation проверяется конечным packet.
- Parent с непустым own body также не включает детей автоматически. Explicit
  source-read whole-section контракт остаётся отдельным пользовательским действием;
  evaluator не должен вызывать его скрыто ради восстановления required answer.
- Links без fragment не означают разрешение загрузить/выдать целый документ:
  фиксируется `document_link_not_expanded`. Это существенный open coverage gap,
  не доказанная ненужность. Никакого fallback на root/subtree.
- External URL: никакого network fetch. В этом минимальном эксперименте automatic
  resolution только local relative fragment/in-document anchors; external link
  отмечается `external_dependency_not_expanded`, даже если тематически похожий
  документ есть в scope. Позднейший URI resolver потребует отдельного контракта.
- Missing/unavailable/ambiguous anchor, duplicate source path/version ambiguity,
  scope/version mismatch — явные gaps; не выбирать первый match. Разрешённый
  dependency target не может стать authority для исключённого module/version.
- Link-like текст в code/fences/comments не dependency. Поддерживаемая syntax
  должна быть явно frozen; unsupported constructs не молча считать полным graph.
- Полные own bodies/conditions/lists/code не режутся. Empty heading не превращать
  в «содержательный факт», но сохранять как структурный контекст при inclusion.

## Receipt, completeness и стоимость

Предлагаемый closure receipt: seed count, dependency-added/ancestor/definition
counts, graph edge count, cycle/dedup counts, gaps по typed reason, source spans
и attribution paths при observer ON. OFF — только bounded aggregate work/gaps,
без нового retained per-score/prompt trace. Полные gap details, необходимые
пользователю для понимания missing evidence, не скрывать ради OFF performance.
Диагностика не должна менять packet, calls или selection.

Различать `scan_complete` (все scorer bodies обработаны), `closure_complete`
(все edges в поддерживаемом closure contract обработаны) и `coverage_unverified`.
Даже closure_complete не означает answer sufficiency. Heading-only/no-fragment/
external gaps не превращаются в successful доказанно полный ответ. Для no-answer:
нулевые seeds дают пустой closure, но нужен полный успешный scan, не overflow/error.
Нельзя требовать отсутствия всех irrelevant document-wide links для no-answer.

Source reduction — прежний pinned source-text codec/union intervals и whole
allowed-original denominator для answerable queries; каждый optional/unlabelled
token входит в numerator. **>=50% aggregate per split неизменно**. Model input
repeats, public packet rendering и source tokens по-прежнему разные метрики.
50k emergency — только typed whole-packet stop; не selection quota и не cropping.
Runtime/graph failure — incomplete/error, не successful partial/empty.

## Версии, fit и smallest diff proposal

Предлагается новая top-level experiment recipe, например
`qwen3-contextual-reference-closure-v1`, с явной ссылкой на unchanged scoring
subcontract и новую structural recipe. Не переименовывать historical Qwen/v2.
Новая schema/policy binding включает structural version, dependency syntax/edge
origin rules, scoring contract/model pins и новый calibration artifacts digest.
Old calibration SHA/policy16fb92... **не являются подтверждением новой closure**.
Новая policy должна пройти новый, отдельно разрешённый fit protocol; не приписывать
старой tau новый смысл и не проводить сейчас counterfactual threshold search.

План минимального diff, не применён:

1. `minimal_context_structure.py`: отдельная v3 closure, роли expandable/auxiliary,
   provenance-preserving definition occurrence resolution, dedup/promotion/gaps;
   build/hydrate/recheck принимает отдельную version, v1/v2 semantics сохраняет.
2. `minimal_context_selection.py`: отдельный dispatch/policy schema, structural
   fingerprint binding; раннее work accounting и error semantics сохраняет.
3. `context_evidence_scoring.py`: только explicit contract/recipe wiring если
   необходимо для независимого fingerprint; inference math/prompt/tokenization
   и model assets не изменять. Предпочесть выделить existing scoring subcontract
   без дублирования scorer; конкретный diff показать до implementation approval.
4. `context_evidence_structure.py`: graph не строить заново по labels/scores;
   при выделении общего syntax resolver доказать неизменность исторического
   scorer JSON/input contract. Не подменять incoming graph selected closure graph.
5. Existing evaluator: независимая graph/obligation representation для fit closure;
   не вычислять oracle тем же production closure. Обновить versioned contract,
   counts/gaps/source metrics. Resource read/replay sequence сохранить.

На implementation review проверить real diff size: если корректная definition
occurrence handling превращается в новый Markdown parser, остановиться и сузить
явно supported syntax по review, а не добавлять ad-hoc regexp fixes для16cases.
No topic dictionaries, semantic quotas, top-k, keyword fallback, новые модели.

## Независимый новый holdout — specification до подготовки/inference

Минимальный proposal: **8 новых questions,2 новых source domains, по4questions**.
На проект4 конкурирующих allowed documents +1 явно excluded scope/version source,
итого10 source files. Это не уже созданный dataset. Documents выбираются по
реальным структурным границам/исходной задаче, не после просмотра scores и не
для искусственного раздутия denominator. Если полного естественного документа
не помещается в32K input, preflight FAIL; не резать его ради заданного результата.

Предпочтительные кандидаты источников для последующего отдельного разрешения:

- SQLite official transaction/locking/isolation documentation (новый domain
  database operation, не synthetic project analogue предыдущих workflow).
- Official Git submodule/worktree/sparse-checkout manuals из одного pinned Git
  source release (новый domain repository state и lifecycle constraints).

Это **кандидаты**, а не уже проверенный inventory: ссылки/anchors/license/version
и подходящие obligations ещё необходимо реально изучить. Сейчас ничего не
скачивалось. Pin commit/release, origin URLs, raw bytes/SHA и extraction rules;
prefer existing locally available upstream originals. Не смешивать rendered HTML
и authored Markdown/AsciiDoc с потерей anchor semantics. Если потребуется lossless
adapter, review и frozen raw→local mapping до любых scoring calls. Не называть
agent-authored conversions внешне независимыми ground truth.

Если предлагаемые upstream docs не содержат нужных мотивов, parent выбирает иной
реальный корпус до freeze; не дописывать удобные links/conditions в source. Малые
agent-authored adversarial fixtures допустимы отдельно как development checks,
не как independent real-source validation. Разные versions/scopes моделируются
реальными snapshot/catalog boundaries, не переименованием неразрешённого текста
в якобы разрешённый source.

### Motif coverage и независимые obligations

Для каждого проекта:3 answerable +1 no-answer. В сумме8 tasks покрывают:

1. Direct rule с local nested conditions/exceptions: обязательны complete own
   body, condition conjunction и negative restriction из оригинала.
2. Cross-document explicit dependency, including indirect chain/definition link:
   обязательны source quote antecedent, target body и его условия/исключения;
   navigation neighbours отдельно reviewed как optional/negative/unlabelled.
3. Broad procedure/heading-only target и ancestor-only linked condition: ожидаемые
   обязательные child bodies перечисляются по independent source reading, с order;
   если выбранный design их теряет, это честный FAIL, не изменение expected set.
4. No-answer с тематически похожими scope/version-excluded sources: empty complete
   scan, отсутствие leaked facts/refs. Answerable version/scope checks также
   проверяют разрешённую версию и явный gap для excluded counterpart.

Motifs можно совмещать в одном вопросе, но не прятать десятки независимых сценариев
в одной hidden loop. Exact questions должны быть естественными user tasks, не
командами «включи секции X/Y» для облегчения механического closure.
Все41 прежних validation facts остаются только seen checks; новые facts нельзя
заимствовать из прошлых answers или генерировать scorer-ом.

Каждый новый task annotation содержит: original query, source identity/version,
verbatim quotes+char spans/hashes, complete required unit bodies, child order,
condition/exception obligations, explicit source-backed relation witnesses,
reviewed true hard negatives и no-answer rationale. Альтернативные equivalent
witnesses только если заранее source-обоснованы; отсутствие точного совпадения
не чинить post-score edits. Parent/human source review labels до freeze.
Unreviewed bodies — unlabelled; их выдача не считается доказанным FP. Полнота
заявляется лишь относительно заранее проверенных obligations, не всего знания
или всех потенциальных dependencies. Optional полезные duplicates не required,
но все tokens учитываются.

Новые domains/upstream authorship улучшают независимость sources от synthetic16,
но agent selection/questions/labels не дают blind external benchmark автоматически.
Лучше parent назначает holdout questions/obligations и удерживает их от изменения
после freeze; developer scorer никогда не получает labels. Ни одного holdout
score до frozen policy и отдельного разрешения. Dataset specification сама по
себе acceptance не является.

## Evaluation protocol и предложенный resource budget

Никакие следующие calls сейчас не разрешены и не выполнены. Предлагаемый staged
budget на parent approval, если design и новый holdout подготовлены:

1. Development fit на старых8 calibration questions:8 public diagnostic scans,
   independent closure-aware largest finite breakpoint preserving required final
   obligations, ties together; no-answer/hard-negative/reduction gates после fit.
   Optional witnesses не снижают tau. При FAIL остановиться, не пробовать другое
   число/модель/инструкцию. Это новый calibration artifact/schema, не reuse old SHA.
2. Только при fit PASS8 real final-policy calls на том же alive root/generation;
   exact offline closure predictions проверить реальным final output. Sources
   и вопросы не менять. Ни одного scorer memo/mock substitution.
3. Старые8 validation questions — отдельные **seen development regression** с
   frozen новой policy. Они не новый holdout и не semantic acceptance сами по себе.
4. Только после parent review предыдущих stages — новый8-question holdout одним
   frozen-policy public run. Новые roots/generations честно записываются.
   Все obligations/gates обязательны; FAIL заканчивает эксперимент, без tuning.

Upper proposal при PASS всех stages: **32 queries,6 prepares** (2 shared prepares
для calibration diagnostic+final,2 seen-regression,2 new holdout). Existing first/
last-source read+replay policy — до **24 resource reads** суммарно, без удаления
проверок lifecycle. Breakdown:8+8+8+8 queries; scorer forwards = число всех checked
nonempty own bodies каждого query (полный scan), без дополнительного model call
на link/closure edge. Точные pair/token/VRAM/time estimates нельзя назвать до
reviewed inventory/tokenization; не обещаем прежние176pairs для нового корпуса.

Model/input costs full scan и repeat final pass учитывать полностью. Graph work
и доставленные unique source tokens отдельно. Preflight full prompts<=32768;
overflow/OOM/runtime errors — incomplete whole scan.50k delivery emergency только
stop. Public in-process proof не объявлять installed/client/provider savings.

## Главные риски / stop criteria

Seed false negative остаётся: если referring evidence вообще не admitted, closure
не начинается. Navigation seeds и cycles/chains способны съесть весь corpus и
экономию. Исключение auxiliary-ancestor expansion может терять реальные условия.
Heading-only/broad child/implicit/no-fragment dependencies всё ещё открыты.
Markdown/HTML anchor ambiguity и authored↔rendered differences могут дать gaps.
Scope/version/native authorization не должна расширяться по graph reachability.
Плохая reduction не оправдывает cropping/heuristic link filters; плохая recall
не оправдывает post-hoc subtree fallback или relabelling. Даже PASS нового малого
holdout — ограниченное evidence, не универсальная достаточность.

**Следующий шаг:** parent review этого candidate design и выбора holdout sourcing.
До отдельного разрешения никаких production/evaluator изменений или model calls.
