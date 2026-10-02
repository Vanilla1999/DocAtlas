# Эвристики DocAtlas: причинный анализ, исследования и проверка упрощения

Дата: 2026-10-02. **Только анализ; production, тесты, thresholds и fixtures не изменены.**

**Уточнение после повторного запуска:**
[проверка механизма Grounded](M2_GROUNDED_MECHANISM_CHECK_RU.md) подтверждает
потери DocAtlas и устанавливает, что Grounded получает required rule уже в
первом индексном chunk, даже при `limit=1`. Neighbor expansion не является
причиной успеха этого результата; 3087 tokens всей выдачи не обязательны.

## 1. Краткий вывод

**Да, есть конкретные основания считать relevance/selection-часть переусложнённой.**
Проблема не в самом существовании эвристик, а в нескольких независимых
приближениях к релевантности без подтверждённой здесь независимой калибровки,
которые последовательно получают
право окончательно удалить контекст. Для `mkdocs-05` это подтверждено trace и
диагностической ablation, а не только впечатлением от размера кода.

Основные выводы:

1. FTS находит нужное правило. Parent diversity и quota теряют его; если устранить
   эту потерю, downstream lexical admission всё равно удаляет кандидат.
2. Доля совпавших слов и соседняя пара слов из вопроса — **не доказательства
   смысла**. Их жёсткое применение отсекает правильную перефразировку.
3. Недавний shared read-context fix выровнял один prefit/final маршрут, но добавил
   ещё один узкий lexical критерий. Восстановление `pydantic-07`/`ruff-07` не
   доказывает его общую пригодность для relevance, paraphrase или cross-language.
4. В коде есть repository-specific boosts и keyword-based source exclusions.
   Это отдельные кандидаты для проверки, а не обязательные identity/scope guards.
   Их причинный вклад в `mkdocs-05` не установлен.
5. Исследования обосновывают сравнение с более простым retrieval baseline,
   релевантностным reranking и измерением answer coverage. **Они не доказывают,
   что предлагаемая переделка исправит именно наш pipeline.**
6. Рекомендуемый объект упрощения — принятие relevance-решений и packing, не
   source/security/freshness/version/snapshot/coverage/permission contracts.

**Доказана причина отказа одного кейса. Универсальное исправление пока не
доказано и в этом шаге не реализовано. M2 остаётся открытым.**

## 2. Что исследовано и как читать степень доказанности

Проверены текущие исходники retrieval → qualification → project prefit →
model-visible projection, сохранённые native/ablation captures и первичные
исследования из раздела 11. Это целевой аудит данного пути, не полный аудит
всех режимов DocAtlas и не исчерпывающий обзор литературы на 2026 год.

| Обозначение | Что считается основанием | Чего оно не доказывает |
|---|---|---|
| **Код** | Действующий predicate, порядок вызовов, коэффициент в working tree | Среднее качество на запросах пользователей |
| **Native trace** | Наблюдение неизменённого pipeline на frozen request/corpus | Причинность без вмешательства, generalization |
| **Offline control** | Другой порядок перед тем же selector вне runtime | End-to-end delivery |
| **Runtime ablation** | Явно обозначенное изменение одного ranking-механизма в диагностическом процессе | Production fix, unseen validation |
| **Исследование** | Результат статьи на её задачах и данных | Автоматическую переносимость результата на DocAtlas |
| **Гипотеза** | Объяснимое направление эксперимента | Подтверждённую пользу или безопасность новой реализации |

Исходники изучены в незакоммиченном working tree; HEAD —
`5a7321987cbe1d9d724a047cf3524c0932e782c8`. HEAD **не является** снимком всех
анализируемых M2 изменений.

Последний сохранённый полный `tests/docs`:
**3382 passed / 104 failed**, `m2_read_context_admission_docs.log`.
Здесь полный suite повторно не запускался. Оставшиеся failures нельзя объявить
целиком obsolete fixtures без классификации. Namespace failures с
`uid_map: Operation not permitted` также не являются PASS.

Docs router вернул `insufficient_evidence`; preparation требует approval и не
выполнялась. Факты о текущей реализации ниже опираются на исходники и captures,
а не на недоступный документационный ответ.

## 3. Не все проверки — одна и та же «эвристика»

Нужно различать четыре вопроса:

| Вопрос | Тип решения | Пример |
|---|---|---|
| Можно ли использовать эти bytes? | Source eligibility / целостность / policy | Правильные project, version, scope, snapshot; нет stale/hard stop |
| Стоит ли показать их для чтения? | Read-context relevance | Есть проверяемый topical context для исходного вопроса |
| Доказывают ли они утверждение? | Claim support / coverage | Видимы субъект, направление relation, условия, необходимые зависимости |
| Можно ли выполнить изменение? | Permission / readiness | Отдельный edit contract и необходимые permissions |

В частности:

```text
safe source       ≠ relevant passage
relevant passage  ≠ supported claim
supported claim   ≠ complete answer
complete answer   ≠ edit permission
```

### 3.1. Что должно оставаться обязательным

- Raw Unicode question, explicit request/scope/version bindings и запреты запроса.
- Проверка identity, source catalog, freshness, lifecycle и snapshot/hash/span.
- Точное соответствие видимого фрагмента исходнику, корректная citation binding.
- Security policy, неисполнение инструкций из document data, permission guards.
- Полный DTO budget, source/module limits и честная partial/missing coverage.
- `request_intent=read` и `lifecycle_intent=current` по умолчанию;
  explicit `change` само по себе не выдаёт permission.

Повторная проверка после clipping нужна: полный исходный chunk мог содержать
условие или отрицание, которых больше нет в показанном окне. **Убрать её ради
«одной проверки» было бы не упрощением, а ошибкой.**

### 3.2. Где даже guard опирается на приближение

Обязательность policy не означает безошибочность её распознавателя.

- Hash/span equality — детерминированная проверка привязки к снимку, но не
  доказательство истинности самого upstream документа.
- `content_trust.py:7–19` ищет instruction-like content по EN regex. Отсутствие
  совпадения не доказывает отсутствие prompt injection на другом языке или
  в другой формулировке. Security guards сохраняются, но их полнота требует
  отдельной adversarial проверки.
- `project_doc_ranking.py:93–128` выводит source lane из keywords вопроса и пути.
  Это heuristic interpretation, даже когда она используется как hard filter.
  Она не эквивалентна explicit scope или проверенной project identity.

Следовательно, нельзя ни удалить всё с `regex`, ни назвать всё с `reject`
формально доказанным security contract.

## 4. Карта действующих эвристик

Упрощённая последовательность исследованного project пути:

```text
raw question / explicit lookups
  → SQLite FTS + ручные score features
  → within-source body ranking + parent diversity
  → source quota + один structural overflow
  → source/reference-bound qualification
  → checked context exemptions для project prefit
  → project reranker и stage budget fit
  → source-local visible variants
  → visible requalification / selection / DTO budget
  → typed context fallback, затем original-read fallback
  → visible snapshot и отдельные support/permission verdicts
```

Это не перечень всех веток hybrid/library retrieval. В частности, для project
chunks dispatcher идёт по body-ranking ветке, а не по library snippet boosts.

| Механизм | Где и что происходит | Аналитическая оценка |
|---|---|---|
| SQLite score tuning | `core/_sqlite_store_part03.py:353–431`: title overlap `+1.5` за term, leading phrase `+2`, boilerplate/authority/length penalties | Объяснимые retrieval features, но их значения не являются доказательством relevance |
| Body-term reranking | `retrieval/_dispatch_part02.py:232–272`: приоритет exact count, затем число разных body terms | Переоценивает все terms одинаково; перестраивает SQLite порядок без сохранения его weighted utility |
| Parent diversity | Там же: первый child каждого parent впереди repeats при том же best exact count и хотя бы одном body term | Структурная новизна подменяет информационную; на `mkdocs-05` доказан harmful interaction с quota |
| Quota/backfill | `_dispatch_part02.py:164–216`: configured quota, плюс один overflow с уже представленным parent при свободной global capacity | Ограничение и rescue взаимодействуют с предыдущим порядком; parent identity не доказывает полноту факта |
| Query terms | `docs/domain/query_terms.py:104–135`: framing vocabulary, length floor 4, technical exceptions, максимум 32 terms | Unicode preservation есть, translation/универсальной segmentation нет; query-length bias возможен |
| Whole-query qualification | `evidence_qualification.py:399–524`: matched/terms; thresholds `1.0`, `0.4`, `0.5`, затем typed admission | Lexical fallback — жёсткий proxy; он не равен semantic entailment |
| Heading/table binding | Там же: heading context после двух body matches; table headers при exact key-cell binding | Полезная защита от metadata-only evidence, но отдельно от semantic correctness |
| Typed local grammar | `admission_grammar.py`, `admission_contract.py`, `need_context_disposition.py` | Бounded RU/EN recognition с unknown/absent/matched; полезна для узких contracts, не универсальный NL reasoner |
| Original-read admission | `application/read_context_admission.py:26–108`: три body terms в одном sentence и adjacent pair из raw question | Новый узкий hard relevance gate; на required paragraph наблюдается false rejection |
| Read-context search caps | Там же, `111–161`: первые 24 candidates, до 16 windows, обычные spans до 640 chars | Resource bounds допустимы; конкретные cutoffs могут снижать delivery и требуют измерения |
| Project intent/source boosts | `project_query_intent.py`; `project_doc_ranking.py:347–372, 676–770` | Смешаны общие preferences и repository-specific правила; целесообразность каждого нужно проверять |
| Prefit veto | `project_doc_ranking.py:680–686`: пустые qualified IDs удаляются без checked exemption | Не просто ranking: ранний отказ лишает final projector возможности рассмотреть кандидат |
| Projection windows | `context_windows.py:130–242`: выбираются term-rich units/windows; есть list/table/fence corrections | Exact spans и целостность структур нужны; term-count objective и размеры windows — проверяемые приближения |
| Final selection | `_docs_context_projection_core.py:238–378, 587–673, 868–937`: requalification, contributions, context proposals, fallback | Обязательна привязка к финальным bytes; сложность relevance orchestration и несколько путей admission — отдельная проблема |

### 4.1. Есть ли действительно «подкрученные» правила?

Да, явно видны правила, привязанные к структуре текущего репозитория:

- `pytest`/`marker` → `docs/testing.md` получает multiplier `4.0`.
- `command` → `wiki/commands.md` получает `3.0`.
- `configuration`-path получает `3.0` для configure/configuration-запроса.
- В project reranker есть path/anchor multipliers `100.0`/`50.0`, exact heading
  phrase `20.0`, дополнительные description/heading overlaps и source weights.
- Source taxonomy/intent знает Docs MCP, Packs MCP, README, architecture,
  roadmap и evaluation paths.

Первые два правила особенно плохо переносимы на произвольный проект. Это факт
по коду, **не доказательство** того, что они ухудшают все запросы или созданы
ради benchmark. Для их удаления нужно отдельное сравнение с baseline.

### 4.2. Explicit-only не означает «вообще нет parsing»

`documentation_query_plan.py:104–170` сохраняет original question и bounded
explicit lookups без guessed natural-language needs/aliases. При этом private
qualification/context classifiers продолжают распознавать роли и relations.

Это разные границы. Существование private typed grammar не доказывает возврат
generated retrieval inference. Но оно означает, что M2 retirement public
inference не устраняет автоматически все relevance heuristics.

Также compatibility ветки и комментарии про retired query origins сами по себе
не доказывают, что эти origins генерируются в текущем runtime request.

## 5. `mkdocs-05`: что именно доказано

Исходный вопрос не переписывался:

> Which page title wins when the navigation configuration and Markdown content define different titles?

Frozen policy: MkDocs **1.6.1**, project scope, source_of_truth, active.
Required witness: `docs/user-guide/writing-your-docs.md:133–135`:

> Note that if a title is defined for a page in the navigation, that title will be
> used throughout the site for that page and will override any title defined
> within the page itself.

То есть navigation title имеет приоритет над title внутри страницы. Запрещено
переносить это на другую version или ненаблюдаемую private configuration.

### 5.1. Native selection loss

Источник: [native capture](m2_mkdocs_discovery_analysis.json).

| Стадия | Candidates | Позиция required paragraph |
|---|---:|---:|
| SQLite output / до body reranking | 51 | 4 |
| Exact supplement | 51 | 4; изменений нет |
| Body ranking с parent diversity | 51 | 15 |
| Source quota/backfill | 3 | Не сохранён |
| Projector input | 0 | Не дошёл |
| Visible packet | 0 sources | Required claim missing |

Quota здесь: `max_sections_per_source=2`, global `limit=20`, `expand='none'`.
Второй preferred slot занимает `Meta-Data` из другого parent. Один разрешённый
overflow занимает ещё один navigation child. Required paragraph — следующий
child этого же navigation parent — уже не получает slot.

**Native trace не показывает qualification отказ required paragraph:** он
раньше потерян. Нельзя приписывать ему downstream reason, которого в native
выполнении не было.

### 5.2. Вмешательство: убрать только parent-diversity promotion

Источник: [runtime diagnostic ablation](m2_mkdocs_no_parent_diversity_ablation.json).
Сохранены original question, corpus, body/exact ranking key, source positions,
quota, global limit и downstream guards. Gold/witness label не участвует в
ordering; используется только observer/scorer.

| Стадия | Native | No-parent-diversity ablation |
|---|---|---|
| Позиция после body ranking | 15 | 4 |
| Required paragraph после той же quota | Нет | **Да, третьим через structural overflow** |
| Original qualification | Не достигнута для witness | `insufficient_visible_match` |
| Typed context classifier | Witness не достигнут | `retrieval_only` / `current_topic_without_complete_proof` |
| Original-read context check | Witness не достигнут | `no_local_topic_witness` |
| Prefit → projector input | 0 | 0 |
| Visible sources / required claim | 0 / missing | 0 / missing |

Это опровергает прежнее предположение «четвёртый абзац всё равно не пройдёт
quota без diversity». Он проходит благодаря существующему overflow.
Но **это не доказательство восстановления delivery**.

### 5.3. Второй барьер: lexical admission и несовпадающие маршруты

Qualification required paragraph в ablation:

```text
matched_terms: page, title, navigation
missing_exact_terms: []
match_ratio: 3/11 = 0.2727
required_ratio для данного lexical fallback: 0.5
reason: insufficient_visible_match
```

В знаменателе также `wins`, `when`, `configuration`, `markdown`, `content`,
`define`, `different`, `titles`. Документ выражает правило через `override`,
а не повторяет вопрос. Длинное описание конфликта в вопросе увеличивает число
terms; короткая правильная формулировка источника не получает достаточно overlap.

Read-only маршрут не создаёт proof/coverage, но требует три terms и adjacent
query pair в том же substantive sentence. Здесь terms есть, нужной пары нет.
`page title` из вопроса не повторяется в форме `title … for a page … override`.
Итоговый отказ — `no_local_topic_witness`.

Private typed classifier для `precedence` допускает paragraph как topical
`retrieval_only`, не как supported proof. Однако prefit exemption вызывает
`set_context_variants` и `iter_read_context_variants`, а не все typed variants:

- `_project_context_service_part01.py:114–146` формирует эти exemptions.
- `need_context_projection.py:184–211` ограничивает set-путь list/set contracts.
- `project_doc_ranking.py:680–686` удаляет оставшийся chunk без qualified IDs.

Поэтому final projector, где существуют precedence proposals и typed fallback,
уже не получает required candidate. **Не установлен отдельный отказ final
projector этому witness: established failure — до него.**

Из этого следует ограниченный causal вывод:

```text
parent diversity + quota → witness исчезает в native run
отмена только diversity → witness сохраняется после quota
qualification/read admission + prefit → witness снова исчезает
```

Для end-to-end восстановления недостаточно исправить только первый барьер.
И два появления одинаковых stage/check rows в capture — не два независимых
статистических испытания.

### 5.4. Не только названия из MkDocs: независимый selection control

В diagnostic script есть synthetic контроль `storage retention timeout`:

| Candidate | Parent | Разные body query terms |
|---|---|---:|
| 0 | A | 3 |
| 1 | A | 3 |
| 2 | A | 2 |
| 3 | B | 1 |

При той же quota:

```text
parent-diverse order: [0, 3, 1, 2]
selected diverse:    [0, 3, 1]
selected plain:      [0, 1, 2]
```

Это воспроизводимый structural контрпример: новый parent с одним совпадением
вытесняет child с двумя. Parent novelty не гарантирует relevance gain.
Но synthetic контроль **не имеет adjudicated semantic answer**, поэтому нельзя
выдать его за измерение answer recall или grounded-correct.

### 5.5. Grounded: полезный контрпример, не равно-бюджетная победа

В сохранённом audit Grounded **3.2.1**, FTS-only, zero embeddings, получает те же
frozen source bytes и original question. При `limit=3` и `limit=5` нужное правило
есть **в Result 1**.

| Grounded native limit | Размер native text, actual `o200k_base` tokens | Required rule |
|---|---:|---|
| 3 | 3087 | Видно |
| 5 | 4488 | Видно |

Raw: `audit/raw/grounded/native/3/mkdocs-05.json` и
`audit/raw/grounded/native/5/mkdocs-05.json`.

Оговорки:

- Это сохранённый comparator audit, не новый запуск на текущем working tree.
- Наш limit 800 — conservative whole-DTO admission:
  `max(ceil(canonical UTF-8 bytes/4), pinned offline codec count)`;
  `model_visible_projection_helpers.py:73–86`. Native text Grounded — другой
  packet, не тот же DTO и не такой же budget contract.
- Grounded не получает весь DocAtlas policy/permission router. Доставка строки
  не означает эквивалентную сертификацию source/answer/edit.
- Reader/LLM ответ на эти два packets здесь не измерялся.
- First-three-paragraph clipping Grounded из старого controlled adapter не
  является native question-directed packing; нельзя считать его честным
  доказательством слабости Grounded при 800 tokens.
- Старый `eval/evidence_quality_v2/protocol.json` указывает Grounded 3.1.0;
  его нельзя смешивать с данным audit 3.2.1.

Вывод, уточнённый повторным запуском: lexical retrieval способен найти материал;
более широкий **индексный chunk** уже содержит правило и получает FTS rank 1.
Query-time expansion не добавляет к первому результату bytes. Подробности и
новый `limit=1` контроль — в [дополнении](M2_GROUNDED_MECHANISM_CHECK_RU.md).
Не доказано ни что FTS решит multilingual delivery,
ни что Grounded лучше на равном бюджете. Подробнее:
[COMPARATORS_RU.md](audit/COMPARATORS_RU.md), разделы 1, 3, 4.

## 6. Почему «эвристика» сама по себе не диагноз

Для произвольного естественного языка нет обещания, что замена regex на
embeddings/LLM даст математическое доказательство правильности. Learned score
тоже является оценкой с ошибками, distribution shift и стоимостью.

Нужна не система «без приближений», а система, в которой:

1. Детерминированные contracts проверяются отдельно от semantic estimates.
2. Relevance features влияют на порядок/выбор с измеренной пользой, а не
   маскируются под proof или универсальную safety boundary.
3. Неизвестное не превращается в supported/permission, но и отсутствие proof
   не автоматически уничтожает пригодный read-only context.
4. Каждый дополнительный механизм оправдан independent ablation и имеет
   фиксируемый failure mode, а не только один regression test.

Примеры пределов текущих proxies:

- Adjacent original-query pair **не необходима** для правильного ответа:
  established `mkdocs-05` witness не проходит её.
- Высокий overlap **не достаточен** для правильного утверждения: два текста
  могут повторять `page`, `title`, `navigation`, но описывать противоположное
  направление priority. Это логический пример, не measured acceptance нового
  payload текущим pipeline; typed checks могут отклонить распознанную форму.
- Parent equality доказывает source-local structure, не семантическое
  дублирование children и не наличие всех необходимых условий.
- Более длинный context может восстановить recall, но увеличивает cost и не
  гарантирует, что reader использует нужный факт.

Особенно опасна комбинация: preference → раннее удаление → fallback-exception
для отдельной формы → новое удаление на следующей границе. Тесты каждого
predicate по отдельности могут быть зелёными при красном delivery.

## 7. Что дают исследования — и чего не дают

| Работа | Установленный результат / предмет исследования | Обоснование для DocAtlas | Предел переноса |
|---|---|---|---|
| **[R1] BM25 and Beyond** | Probabilistic relevance framework, term weighting, metadata/structure features, parameter optimization | Rank utility нужно отличать от proof; сравнивать новые unweighted overlap features с weighted retrieval baseline | Не доказательство конкретных наших коэффициентов или thresholds |
| **[R2] BEIR** | 18 heterogeneous datasets; BM25 — robust baseline; reranking/late interaction сильны в среднем zero-shot, но дороже | Начать с сильного простого baseline и измерять domains отдельно; не считать dense retrieval обязательным лекарством | Не docs-specific benchmark с нашими budgets/guards; улучшение не гарантировано |
| **[R3] MMR** | Баланс query relevance и novelty; параметр регулирует trade-off | Diversity не должна автоматически доминировать relevance; проверить controlled redundancy penalty вместо parent-first promotion | MMR тоже approximate objective с tuning; не гарантирует answer coverage или выигрыш на нашем corpus |
| **[R4] JPR** | Joint passage reranking для нескольких разных ответов; улучшение answer coverage на трёх multi-answer datasets | Сравнивать набор полезных passages, а не только diversity разделов или score каждого по отдельности | Multi-answer задача отличается от нашего precedence/condition proof; внедрение JPR не предлагается как готовое решение |
| **[R5] Selective QA** | Calibration under domain shift; softmax confidence alone даёт худший risk/coverage trade-off | Читать false abstention вместе с wrong/unsupported rate; lexical ratio нельзя считать calibrated confidence | QA benchmark не сертифицирует project/source/security policy и не задаёт наш допустимый risk |
| **[R6] ALCE** | Отдельные correctness и citation-quality metrics; остаются ошибки и неполная поддержка citations | Доставка текста, source binding и claim support должны измеряться отдельно | Automatic NLI/citation evaluator может ошибаться; он не formal proof и не edit authorization |
| **[R7] Lost in the Middle** | Reader performance зависит от положения evidence в длинном context | Увеличение context budget не универсальное исправление; нужен reader experiment и контроль position/cost | Конкретные модели/задачи статьи не дают численного прогноза для нашего reader |
| **[R8] MIRACL** | Human relevance judgments для monolingual retrieval в 18 языках | Нужны per-language judgments/metrics; Unicode-safe regex не равен multilingual relevance | MIRACL именно monolingual, не доказательство RU-query → EN-doc retrieval |
| **[R9] XOR QA** | Cross-lingual retrieval/reading на 7 non-English languages; выделены retrieval, span и full-answer задачи | Cross-language delivery тестировать отдельно; сравнивать explicit lookups и multilingual scoring при неизменном raw question | Translation baselines статьи не разрешают возвращать server-generated aliases/rewrite в explicit-only M2 |
| **[R10] IR significance tests** | Сравнение paired tests на TREC runs; test statistic должен соответствовать reported metric | Парные comparisons, uncertainty и заранее выбранная primary metric вместо зелёного счётчика | Не готовый power calculation для наших немногих project clusters |

### 7.1. Что из литературы действительно следует

Есть исследовательское основание проверить:

- weighted retrieval baseline без дополнительных repository-specific ranking
  правил;
- relevance-first selection с измеряемой redundancy penalty;
- один standalone read-context admission contract, отличный от proof;
- joint coverage/packing для составных facts;
- measured selective risk/coverage и отдельную multilingual панель.

Но не следует ни «удалить qualification», ни «снизить 0.5», ни «добавить wins →
override словарь», ни «embeddings всё докажут». Все четыре варианта либо обходят
contracts, либо добавляют новую необоснованную зависимость.

### 7.2. Пример явного objective вместо набора исключений

MMR [R3] выбирает следующий passage по objective:

```text
λ · Rel(query, passage) − (1 − λ) · max Sim(passage, already_selected)
```

При `λ=1` остаётся relevance ranking; уменьшение `λ` увеличивает штраф за
redundancy. В нашей parent-first promotion явного trade-off по степени relevance
нет: при одинаковом best exact count новый parent с одним body term может
оказаться впереди repeat с несколькими terms.

Преимущество явного objective — возможность заранее определить baseline,
изолировать penalty и измерить его пользу/вред. Это **не** преимущество,
доказанное для DocAtlas. `Rel`, `Sim` и `λ` тоже требуют проверки; структурная
близость children не должна автоматически считаться semantic redundancy.
При tight budget дополнительно нужно учитывать реальный DTO cost и зависимые
facts. Формула MMR сама по себе эту задачу не решает.

## 8. Переусложнили ли код?

### 8.1. Наблюдаемая сложность, а не произвольный рейтинг

В 14 выбранных модулях из таблицы ниже: **5365 строк, 138 function definitions,
571 `ast.If` nodes**. Включены комментарии/blank lines и вложенные functions;
`if` counts включают вложенные функции, но не conditional expressions.
Это reproducible static inventory, **не cyclomatic complexity**, не latency
measurement и не доля «лишнего кода».

| Файл | Строк | `ast.If` |
|---|---:|---:|
| `docmancer/core/_sqlite_store_part03.py` | 665 | 47 |
| `docmancer/retrieval/_dispatch_part02.py` | 364 | 40 |
| `docmancer/docs/domain/query_terms.py` | 235 | 16 |
| `docmancer/docs/domain/project_query_intent.py` | 225 | 16 |
| `docmancer/docs/domain/project_doc_ranking.py` | 880 | 177 |
| `docmancer/docs/domain/evidence_qualification.py` | 613 | 64 |
| `docmancer/docs/domain/admission_grammar.py` | 238 | 14 |
| `docmancer/docs/domain/admission_contract.py` | 84 | 7 |
| `docmancer/docs/domain/context_windows.py` | 389 | 43 |
| `docmancer/docs/application/need_context_disposition.py` | 182 | 23 |
| `docmancer/docs/application/need_context_projection.py` | 211 | 25 |
| `docmancer/docs/application/read_context_admission.py` | 186 | 22 |
| `docmancer/docs/application/context_query_probes.py` | 93 | 7 |
| `docmancer/docs/application/_docs_context_projection_core.py` | 1000 | 70 |

Особенно широкие функции:

- `project_docs_context`: строки 65–794, **730 строк / 53 `ast.If`**.
- `rerank_project_doc_chunks`: 624–880, **257 строк / 29 `ast.If`**.
- `_focused_snippet`: 130–242, **113 строк / 15 `ast.If`**.

Некоторые выбранные файлы содержат hydration/compatibility/helpers, а не только
эвристики. Их суммарный размер нельзя приравнять к removable relevance logic.

### 8.2. Более сильное основание, чем число строк

**Архитектурные симптомы подтверждаются кодом и trace:**

1. **Несогласованные predicates одного назначения.** Typed context route
   допускает current topic при двух body terms; original-read route требует
   три terms + pair; prefit сохраняет не все typed shapes.
2. **Слишком ранние irreversible veto.** Final precedence proposal не может
   спасти candidate, удалённый prefit. Общий final fallback не решает потерю
   candidate inventory.
3. **Несколько objectives.** SQLite weighted utility, body-term count,
   parent novelty, source weights, public-query direction counts и term-rich
   windows последовательно оптимизируют разные proxies.
4. **Разные lexical views.** SQLite trace использует свой term/field extraction;
   `documentation_query_terms`, fallback probe terms и window scoring — другой.
   В capture SQLite exact list включает `markdown`, а downstream exact list
   пуст. Это не автоматически bug: retrieval anchor и hard identity могут
   различаться. Но их нельзя без пояснения объединять в один «match score».
5. **Cross-layer coupling.** `read_context_admission` обращается к private
   helpers typed-context/projection и qualifier; qualifier одновременно
   проверяет source, lexical fields и typed witness. Изолированно менять
   relevance policy трудно.

Итог: **есть избыточная сложность orchestration и policy overlap**. Не доказано,
что её следует лечить удалением всех typed contracts или заданного процента
кода. Простое разбиение большого файла не устранит ни один causal failure.

## 9. Предлагаемое направление упрощения — только гипотеза

Не рекомендуется добавлять ещё один MkDocs/precedence exception. Проверяемая
архитектура могла бы выглядеть так:

```text
immutable RequestContract + prepared SourceSnapshot
  → bounded candidate retrieval
  → finite exact-span structural alternatives
  → shared EligibilityCheck
  → shared ReadRelevanceDecision (context, не proof)
  → один bounded packing/selection objective
  → recheck текущих visible bytes и полного DTO
  → отдельные ClaimSupport / Coverage / Permission decisions
```

### 9.1. Что это должно означать в реализации

- Source eligibility проверяется единым контрактом, но **повторно на каждой
  изменившейся source/window boundary**, а не один раз навсегда.
- Prefit и final используют одну версию read admission и один candidate
  identity/span contract. Provisional prefit result не является final approval.
- Relevance score не выдаёт qualified IDs, root coverage, proof или permission.
  Само присутствие безопасного источника/высокого retrieval score недостаточно:
  standalone read admission всё равно обязателен.
- Обычный read relevance проверяется независимо от того, распознан ли вопрос
  как enumeration/precedence/default. Если conditions/identities не проверены,
  система не выдаёт их за сохранённые и не ослабляет соответствующий veto.
- Structural atoms сохраняют целые rows/items/conditions. Не вводятся
  full-parent rescue, новые source reads или unbounded expansion.
- Diversity — проверяемая preference, не безусловное право нового parent
  потратить slot. Configured quotas/budgets остаются теми же.
- Provenance и explicit policy берутся из verified metadata, а не заменяются
  keyword classification. Heuristic taxonomy может быть preference; изменение
  source-policy semantics требует отдельного решения и не входит в этот шаг.
- Typed proof сохраняется для поддерживаемых relations. Unknown остаётся
  unknown; retired generated queries/needs/probes/aliases не возвращаются.

Это проектная рекомендация, а не готовый plan с доказанной совместимостью.
Самая трудная часть — **чем именно заменить некалиброванный lexical veto для
read relevance**, сохранив subjects, constraints и отрицательные controls.

### 9.2. Какие кандидаты сравнить

1. **Простой baseline:** существующий lexical retrieval, deterministic dedupe,
   exact source-local atoms и unchanged bounds. Дополнительные body/diversity/
   repository boosts по отдельности отключаются только в experiments.
2. **Shared typed/topic admission:** проверить согласованный prefit/final
   contract. Уже существующий typed floor не является автоматически хорошим
   универсальным решением; он тоже нуждается в negatives и language evaluation.
3. **Один learned reranker/read-relevance scorer:** только после baseline;
   pinned model/version, independent judgments, explicit uncertainty, без
   использования model score как claim proof. Нет нового query generation.

Даже идеальный reranker не восстановит passage, которого уже нет в его входе.
Поэтому сравнивать нужно candidate retention и admission вместе, не заменять
только последний score.

## 10. Как получить доказательство исправления, а не ещё один patch

### 10.1. Уже есть и ещё нет

| Проверка | Статус | Допустимый вывод |
|---|---|---|
| Native `mkdocs-05` | Есть | Selection loss и missing delivery наблюдаются |
| Offline same-quota alternative orders | Есть | Quota может сохранить required paragraph при другом порядке |
| Runtime no-parent-diversity ablation | Есть | Первый барьер снимается, downstream отказ остаётся |
| Synthetic generic selection control | Есть | Parent-first preference может вытеснить более term-matched child |
| Grounded native witness check | Есть | Другой retrieval/packing доставляет правило в большем packet |
| Candidate end-to-end fix | **Нет** | Нельзя объявлять исправление |
| Unseen validation нового решения | **Нет** | Нельзя утверждать generalization |
| Equal-budget Grounded comparison с адекватным packer | **Нет** | Нельзя утверждать comparative superiority |
| Reader risk/coverage для предлагаемого упрощения | **Нет** | Нельзя утверждать improved grounded answers |

### 10.2. Минимальный причинный factorial experiment

После отдельного approval — не в этом analysis-only шаге:

| Arm | Parent preference | Read admission | Назначение |
|---|---|---|---|
| A | Current | Current | Контроль |
| B | Без parent-first promotion | Current | Уже наблюдаемый selection-only эффект |
| C | Current | Candidate shared standalone relevance | Изоляция admission эффекта; ранняя retrieval loss остаётся возможной |
| D | Без parent-first promotion | Тот же candidate relevance | Проверка взаимодействия и end-to-end retention |

Candidate relevance сначала специфицируется, а не подбирается по результату
`mkdocs-05`. Это **не** снижение existing qualification thresholds: old proof/
coverage verdicts и permissions остаются независимыми. Нельзя разрешать context
просто потому, что old qualification отказал.

У всех arms одинаковы requests, frozen source bytes/policy, expansion mode,
candidate limits, quota/overflow, source/module caps, full-DTO budget и guards.
Никакого gold-dependent selection. Если candidate нужны другие limits, это
другая заранее названная cost/recall ablation, а не «тот же эксперимент».

Далее отдельные ablations для repository-specific boosts, lexical score tuning
и окна packing. Не отключать всё одновременно: иначе причинность потеряется.

### 10.3. Какие данные нужны

- Неизменённые original cases, включая `mkdocs-05`, `httpx-07`, `pydantic-07`,
  `ruff-07`; exposed benchmark — regression/development evidence.
- Новые held-out projects, topics и independently authored paraphrases без
  keyword dictionaries под известные answers. Не менять старые questions/gold.
- Separate monolingual и cross-lingual strata: EN→EN, RU→RU, RU→EN и другие
  заявленные языковые пары; natural native-speaker questions, не только
  переводы известных EN формулировок.
- Negative controls: heading/link-only, generic shared words, quoted question,
  wrong subject/version/scope/project, stale/changed snapshot, missing
  prerequisite, polarity reversal, `only/unless/except/without`, prompt injection.
- Counterexamples для списков/таблиц, conflicting rules и нескольких источников:
  один relation не должен выигрывать за счёт потерянного condition или key cell.
- Unknown/compound tails: известный partial context сохраняется **только если**
  неизменны scope, identity, version, applicability, conditions и prohibitions;
  private unknown остаётся unresolved. Это не blanket monotonicity для любых
  добавлений к вопросу.

`cases.json` помечает `mkdocs-05` как `frozen_validation_exposed`.
Этот кейс не становится unseen validation от замораживания повторного запуска.

### 10.4. Метрики по границам, а не один PASS count

Для каждого request сохранить решения и exact spans после каждой стадии.
Различать:

1. **Candidate witness recall:** supporting span найден до selection.
2. **Retention:** supporting span сохранился после diversity/quota/prefit.
3. **Budgeted evidence completeness:** все adjudicated supporting parts видимы
   в финальном packet, причём возможен union нескольких spans.
4. **Read-context precision:** independently judged useful/admissible packets
   среди доставленных; нерелевантный safe context тоже является ошибкой relevance.
5. **False abstention:** frozen answerable case получил missing packet/отказ.
6. **Unsupported/wrong support:** необоснованное поднятие support/coverage flags;
   отдельно от ошибок LLM reader.
7. **Reader grounded-correct, citation correctness/completeness, risk/coverage**
   на одних и тех же model, prompt, sampling и evidence budgets.
8. **Guard violations:** wrong identity/version/scope/snapshot, unsafe admission,
   budget overflow и unauthorized permission — отдельные blocking outcomes.
9. **Cost/complexity:** actual common-tokenizer whole packet, latency p50/p95,
   candidate/window counts, scorer calls, изменённые predicates/branches и
   исключения. Cold/warm measurements и repetitions заранее фиксируются.

Safety regression tests не оценивают semantic relevance. Semantic judge не
оценивает source binding автоматически. Автоматический scorer может давать
false negatives на formatting/union evidence — нужен blind independent review;
`needs_review` не считать PASS.

### 10.5. Критерий приёмки

Два разных уровня доказательства:

**Contracts/invariants:** source-span binding, budget enforcement, identity/
scope/version policy, non-escalation permissions. Проверяются deterministically,
property/adversarial tests и trace validation. Они не доказывают общий смысл NL.

**Semantic usefulness:** парный эксперимент на независимых judgments с
confidence intervals и заранее заданными metrics/margins. Положительная
точечная разница на exposed cases недостаточна.

До запуска зафиксировать practically meaningful improvement/non-inferiority
margins, uncertainty method и cost ceiling. Для project-correlated cases
ресемплировать project clusters, а не считать сотню paraphrases одного проекта
сотней независимых samples. При малом числе clusters вывод о generalization
слабый; нужен размер панели, обеспечивающий достаточную мощность.
Если проверяется много arms, нужен preselection или multiple-comparison control.
Это рекомендация методологии, не новые M2 acceptance thresholds.

Обязательные условия для предложения production fix:

- Required witness `mkdocs-05` доставлен при прежнем полном DTO budget; source
  binding и unchanged request/policy подтверждены end-to-end.
- Полезный прирост или non-inferiority на held-out panel, не только известный
  case; preservation `httpx-07`/`pydantic-07`/`ruff-07` и других partial cases.
- Нет guard/permission regressions, unsupported rate не ухудшился по заранее
  определённому критерию. Ноль observed violations не доказывает нулевой риск
  вне проверенного набора.
- Объяснено, почему уменьшено число независимых policy decisions/exceptions;
  short-code diff сам по себе не acceptance criterion.
- Все 104 нынешних failures классифицированы для M2 gate; environment limits
  явно отмечены. Нельзя объявить M2/M3/M4 завершёнными по одному evidence case.

## 11. Первичные исследовательские источники

Ссылки проверены при подготовке отчёта. Ни одна из работ не исследует текущий
DocAtlas working tree; архитектурные рекомендации выше — наш вывод из их
результатов и локальных observations, а не цитируемая готовая гарантия.

- **[R1]** Stephen Robertson, Hugo Zaragoza. **The Probabilistic Relevance
  Framework: BM25 and Beyond.** Foundations and Trends in Information Retrieval,
  2009, 3(4):333–389. [DOI](https://doi.org/10.1561/1500000019),
  [авторский PDF](https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf).
  Для анализа: introduction, BM25/metadata features и parameter optimization.
- **[R2]** Nandan Thakur et al. **BEIR: A Heterogeneous Benchmark for Zero-shot
  Evaluation of Information Retrieval Models.** NeurIPS Datasets and Benchmarks,
  2021. [Paper, v4](https://arxiv.org/abs/2104.08663v4).
- **[R3]** Jaime Carbonell, Jade Goldstein. **The Use of MMR, Diversity-Based
  Reranking for Reordering Documents and Producing Summaries.** SIGIR, 1998.
  [Авторский PDF](https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf).
  Для анализа: §2, управляемый relevance/novelty trade-off. Не смешивать с
  отдельным ACL workshop abstract тех же авторов.
- **[R4]** Sewon Min et al. **Joint Passage Ranking for Diverse Multi-Answer
  Retrieval.** EMNLP, 2021, pp. 6997–7008.
  [ACL / DOI](https://aclanthology.org/2021.emnlp-main.560/).
- **[R5]** Amita Kamath, Robin Jia, Percy Liang. **Selective Question Answering
  under Domain Shift.** ACL, 2020, pp. 5684–5696.
  [ACL / DOI](https://aclanthology.org/2020.acl-main.503/).
- **[R6]** Tianyu Gao et al. **Enabling Large Language Models to Generate Text
  with Citations.** EMNLP, 2023, pp. 6465–6488.
  [ACL / DOI](https://aclanthology.org/2023.emnlp-main.398/),
  [full text](https://arxiv.org/html/2305.14627v2), §3 evaluation dimensions.
- **[R7]** Nelson F. Liu et al. **Lost in the Middle: How Language Models Use
  Long Contexts.** TACL, 2024, 12:157–173.
  [ACL / DOI](https://aclanthology.org/2024.tacl-1.9/).
- **[R8]** Xinyu Zhang et al. **MIRACL: A Multilingual Retrieval Dataset Covering
  18 Diverse Languages.** TACL, 2023, 11:1114–1131.
  [ACL / DOI](https://aclanthology.org/2023.tacl-1.63/).
- **[R9]** Akari Asai et al. **XOR QA: Cross-lingual Open-Retrieval Question
  Answering.** NAACL, 2021, pp. 547–564.
  [ACL / DOI](https://aclanthology.org/2021.naacl-main.46/),
  [full text](https://arxiv.org/html/2010.11856v3), §3 task separation.
- **[R10]** Mark D. Smucker, James Allan, Ben Carterette. **A Comparison of
  Statistical Significance Tests for Information Retrieval Evaluation.** CIKM,
  2007, pp. 623–632. [DOI](https://doi.org/10.1145/1321440.1321528),
  [авторская публикация](https://ciir-publications.cs.umass.edu/getpdf.php?id=744).

## 12. Локальные основания и воспроизводимость

Основные artifacts, без нового production вмешательства:

- [Observer script](m2_mkdocs_discovery_analysis.py): wrappers вызывают исходные
  functions; только `--no-parent-diversity` включает названное вмешательство.
- [Native capture](m2_mkdocs_discovery_analysis.json): `summary`, `stages`,
  `offline_same_quota_selections`, `synthetic_selection_control`.
- [Ablation capture](m2_mkdocs_no_parent_diversity_ablation.json): дополнительно
  `qualifications`, `context_checks`, `projection_candidate_counts`, `claims`.
- В обоих captures corpus hash:
  `8cd3601264f74664fecd51dcd467b7de369d44e9b09bd2751f242dd6a6ddab3d`.
- [Frozen cases](../../eval/evidence_quality_v2/cases.json), строки 2107–2144.
  Annotated witness envelope — 134 estimated tokens/1 source; это не measured
  runtime DTO успешной доставки. Runtime fit нового решения ещё надо доказать.
- [Последний read-context fix](M2_READ_CONTEXT_ADMISSION_FIX_RU.md),
  [полный docs log](m2_read_context_admission_docs.log),
  [migration status](MIGRATION_STATUS_RU.md).
- [Comparator conditions](audit/COMPARATORS_RU.md) и raw Grounded packets выше.

Ранее `M2_READ_CONTEXT_ADMISSION_FIX_RU.md` описывал remaining `mkdocs-05` как
discovery-cap loss. Это верно для native first divergence, но **не полный
causal analysis**: no-diversity runtime ablation обнаружила второй барьер.
Настоящий отчёт уточняет вывод, не переписывая старые artifacts.

Для повторения diagnostics в настроенном repository environment:

```bash
PYTHONPATH=. python roadmap/search-quality-2026-10-01/m2_mkdocs_discovery_analysis.py
PYTHONPATH=. python roadmap/search-quality-2026-10-01/m2_mkdocs_discovery_analysis.py --no-parent-diversity
```

При первоначальной подготовке этого отчёта captures только прочитаны. При
последующей проверке Grounded повторены существующие native/no-parent-diversity
DocAtlas diagnostics, а также Grounded ingest/search и expansion control;
результаты — в [дополнении](M2_GROUNDED_MECHANISM_CHECK_RU.md). Production fixes,
новый полный regression run и commit/push/merge не выполнялись.

## Итоговая рекомендация

**Не наращивать исключения. Сначала доказать пользу упрощённой relevance/
packing архитектуры на unchanged contracts и независимых данных.**

Известный failure уже показывает лишнее пересечение relevance veto и
несогласованность стадий. Он не оправдывает ослабление guards и не даёт права
назвать очередной lexical rule научно доказанным исправлением.
