# Proposed contract: source-grounded occurrence dependency classification

**Статус: DESIGN / parent review required.** Выбран один следующий метод:
отдельный learned relation component с source-backed witnesses и обязательным
abstention, поверх детерминированного closure. Модель не выбрана, качество не
установлено, calls разрешено **0**. Это новый непроверенный subcontract, не новая
instruction существующему unary reranker и не продолжение его validation.
V3 остаётся PRE-INFERENCE BLOCKED, manifest
`b5b955b82a930dda810cdbffdf27fb3350f33065c6f0eb4f7a2f916d5e76d817` неизменен.
Основание пересмотра — `../step10-reference-closure-v3/FEASIBILITY_BLOCKER_RU.md`:
all-reference closure раскрывает TOC и недоступные зависимости независимо от
качества seed scoring. Это design limitation, не scorer FAIL.

## 1. Что теперь значит completeness

Предлагается **task-and-delivered-claim completeness**, а не полнота всего графа
гиперссылок. Успешный пакет должен содержать обязательные факты исходной задачи
и все необходимые условия, определения и исключения для корректного понимания
каждого доставленного утверждения. Есть два независимых основания зависимости:

1. Target нужен для выполнения исходной пользовательской задачи через данное
   source-backed отношение.
2. Target нужен для интерпретации условия, ограничения, исключения или значения
   уже доставленного утверждения, даже если само утверждение побочно для вопроса.

Любое основание требует включения. «Irrelevant to query» не разрешает потерять
qualifier доставленного текста. Обычная библиография или навигация может остаться
буквальной цитируемой ссылкой без target body, только если обосновано отсутствие
**обоих** оснований. Links, source text и whole bodies не удаляются/не переписываются.
Generated answer не участвует ни в selection, ни в oracle, ни в обратной связи.

Одинаковое правило применяется к seeds, ancestors, addressed children и
definition-owner bodies. Исключений по admission role нет. Required heading target
по-прежнему означает полный author section extent с children и ancestors;
document target — полный checked document. Ownbody-only targets не возвращаются.
Completeness — проверяемое требование продукта, но предсказание relation component
само по себе не доказательство его выполнения и не гарантия на произвольном corpus.

## 2. Occurrence contract и разрешение пропуска

Единица решения — **конкретное употребление ссылки**, не URL/target вообще.
Минимальный record содержит:

| Поле | Содержание |
|---|---|
| Identity | project/scope/version/generation, source path/hash, body identity |
| Occurrence | literal link и Unicode char `[start,end)`; claim/block span; definition-use связь при наличии |
| Context | exact original question; полные source document и enclosing structure; доступный target full addressed extent + ancestors и полный checked target document как интерпретационный контекст |
| Resolution | normalized destination; native-qualified target identity/hash/extent либо typed unavailable/ambiguous/unsupported status |
| Decision | `REQUIRED`, `NONBINDING`, `UNKNOWN`; основания task/claim отдельно: yes/no/unknown |
| Witnesses | дословные source spans/hash для claim, его отношения к target и обоснования решения; target spans только при разрешённом доступе |
| Provenance | relation contract/model/prompt/tokenizer revision, input digest, validation outcome |

Полный source document нужен для условий вне ближайшей строки; полный target
document — для контекста addressed extent, а не автоматической выдачи всего
документа при anchor link. Разрешённые контексты фиксируются до решения, не
собираются из текущего delivered set. Вывод содержит краткое source-grounded
основание, не свободное сочинение target contents. Проверяется, что spans внутри
соответствующих hashes, цитаты буквальны, все input blocks целиком помещаются в
context window. Проверка offsets подтверждает provenance, **не логическую верность**.

`REQUIRED`: хотя бы одно основание yes. `NONBINDING`: оба no, валидные witnesses,
полный требуемый контекст и успешная schema/provenance validation. Всё остальное,
включая конфликт, недостаток контекста, превышение окна, сбой классификации,
неподдержанный parse — `UNKNOWN`. Confidence сама по себе не разрешает skip.
Нет keyword lists («MUST», «overview», «see also»), правил domain/filename/questionid
или старого Qwen threshold на targets. TOC/HTML nav markers — лишь source evidence:
смешанный block может содержать обязательное условие внутри списка ссылок.
Чистое structural TOC исключение уменьшило бы часть blowup, но не отличило бы
обычные нормативные ссылки от справочных и могло бы потерять такое условие.

Недоступный target не передаётся модели и не восстанавливается по памяти.
Source-only решение `NONBINDING` допускается для явно обоснованной обычной
библиографической/навигационной функции, если оба отрицательных основания можно
установить без target. Отсутствие доступа само по себе таким свидетельством не
является: при зависимости от неизвестного содержания — `UNKNOWN`. Внешняя
нормативная зависимость — `REQUIRED`/incomplete; внешняя citation не обязана
блокировать, если source-only обоснование действительно достаточно.

Reference use всегда сохраняет whole definition-owner body для буквального
разрешения source syntax; outgoing links owner классифицируются на общих правах.
Code-formatted label limitation (`[` + inline code + `]`) означает `UNKNOWN`,
не «ссылки нет». Unsupported syntax, обнаруженная внутри admitted body, создаёт
parse obligation. Если невозможно достоверно локализовать потенциальные links,
весь affected body имеет UNKNOWN parse scope; его нельзя объявить complete через
классификацию только распознанных ссылок.

## 3. Детерминированный fixpoint и отказы

1. Existing полный seed scan выбирает own bodies + ancestors. Никакой relation
   classifier не исправляет пропущенные семантические seeds по generated answer.
2. Для каждого admitted body перечислить occurrences/definition bindings и parse
   obligations. Решение вычисляется на immutable snapshot, один раз на exact key.
3. `REQUIRED` или `UNKNOWN` с однозначным available qualified target добавляет
   **весь** addressed extent + ancestors; document link — весь document. У всех
   добавленных bodies раскрываются следующие occurrences по тому же правилу.
4. `NONBINDING` не добавляет target, оставляет literal link. Если target добавлен
   другой required occurrence, он остаётся: negative decision ничего не удаляет.
5. REQUIRED/UNKNOWN unavailable, scope/version mismatch или неразрешимый parse
   scope даёт body-free `dependency_incomplete`. Доставка known target покрывает
   UNKNOWN отношение, но не исправляет отдельно неизвестную parse/resolution
   границу. Успех требует отсутствия непокрытых obligations.

Монотонное добавление, source-stable queue/order и dedup по full native identity;
cycles завершаются на конечном snapshot без depth/top-k caps. Key включает question,
все source/target/context hashes и identities, occurrence spans, parser/relation
revisions. Admission role, queue order, seeds order, scores, reduction budget и
label IDs не являются inputs. Нельзя повторно оценивать отношение с меняющимся
delivered context: это породило бы немонотонность и неверный cache reuse. До
интеграции требуется воспроизводимость решений на pinned inputs; конфликт повторов
консервативно UNKNOWN, не выбор удобного результата. Cache reuse требует полного
key match и повторной native live qualification; новый snapshot — новый key.

Unselected full-context gaps остаются diagnostics. Empty-seed successful complete
scan/no-answer проверяется отдельно и не наследует их; scan failure и dependency
refusal не no-answer и не successful token saving.

## 4. Capability gate и независимое доказательство

До production implementation отдельным разрешением нужны source-annotated
development relations и capability experiment компонента: понимает ли он два
основания, различает ли paired occurrences, выдаёт ли проверяемые spans, abstains
при missing context и выдерживает context fit/стабильность. Сейчас ни выбор модели,
ни набор данных, ни вызовы не разрешены. Existing 16 synthetic + 8 OTel/Rust tasks
теперь **seen development**; 39 проверенных quotes сохраняют требования, но не
валидируют новый classifier. Prior unary Qwen policies не relation calibration.

Независимый oracle размечает source relations до model calls, без production
closure/ответов модели как эталона. Parent review утверждает decision, два
основания, raw witnesses и required full extents. Unlabelled не negative;
неопределённый gold — UNKNOWN. Нужны реальные новые задачи с paired contrasts:
один target как nav и binding use; ancestor condition; requirement внутри apparent
TOC; child exceptions; generic «details» как necessary без norm words; external
citation против отсутствующего normative condition; native scope/version mismatch.
Обязательны и истинные safe-to-omit targets, и required positives. Поддержка
source-only NONBINDING для unavailable targets проверяется отдельно.

Freeze sources целиком, scope, questions, oracle, model inputs, decision policy,
budget и acceptance criteria **до** model calls. Не обрезать original corpora ради
fit и не заменять после scores. Если выбран abstention threshold, калибровать
только development; после фиксации — ровно одна heldout check, без retuning на ней.
Отдельный public integration gate через реальные native storage/selection/closure
и delivery проверяет конечные bodies/facts/hash/span/scope/version, no-answer,
refusal и safe omission. Не unit matrices и не mocked relation results как
доказательство качества. Выполнить дефектную omission в публичном сценарии должно
означать обнаружимый FAIL, а не только совпадение внутренних flags.

Acceptance conjunctive: zero known missed mandatory edges; zero required facts
lost; все true safe-to-omit witnesses обоснованы; UNKNOWN корректно покрыт/отказан;
исходные whole-unit/task gates сохранены; минимум50% source reduction на заранее
зафиксированном successful-answer denominator. Refusals нельзя выкинуть из task
acceptance или засчитать как экономию. Нулевые ошибки на finite gate — эмпирическое
свидетельство, не гарантия universal necessary-link inference.

## 5. Стоимость, smallest future diff и stop rule

Считать отдельно unchanged full seed scan и новые relation prompts: cold/hit cache,
число unique occurrences/actual calls/repeats, input/output/provider tokens,
latency и failures; source delivered tokens — отдельная метрика. Повторные source
documents в relation prompts могут стоить больше сэкономленных source tokens.
Без caps emergency останавливает обработку с явным отказом, а не тихо пропускает
edges. Полный context не помещается — UNKNOWN/fallback, не crop и не пересборка
corpus ради PASS.

Будущий минимальный opt-in diff: отдельные relation subcontract/recipe/schema и
policy binding; occurrence receipts/cache; versioned closure dispatch; independent
public evaluator/oracle adapter. Existing scorer inputs не менять; blocked V3 и
его artifacts не переписывать/не переименовывать в новый успех. Нужен общий
bounded finalization **для всех return paths**: parent выявил обход50k guard в V3
`minimal_context_selection.py:211–217` при dependency_incomplete early return.
В будущем исправление отдельным reviewed diff: body-free error тоже ограничен
metadata/wire budget; bounded counts+digests, truncation indicator и отдельно
доступная полная diagnostic trace вне protocol stdout. Нельзя считать отсутствие
перечисления всех gaps их отсутствием. Проверять emergency/refusal публично.

**Stop rule:** без reviewed oracle, возможности полного контекста, стабильных
source-backed решений и capability gate production implementation не начинать.
Если classifier путает обязательные qualifiers с navigation или abstention делает
50% gate недостижимым, остановиться с конкретным результатом; не ослаблять facts,
не вводить hidden heuristics. Generic необходимую ссылку гарантированно выводить
из произвольного текста этот design не умеет. Остаточный риск — ошибочный
NONBINDING с правдоподобной цитатой; offset validator его не устраняет. Предлагается
проверяемый эксперимент с fail-closed UNKNOWN, а не обещание общего решения.

Текущий итог: только этот design document; implementation/data/runtime work не
разрешена. Следующий шаг — parent review изменения product completeness и
условий отдельного capability experiment, а не автоматический inference.
