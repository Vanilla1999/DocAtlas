# 07. Проверить причины потери read context и выбрать одну замену

Статус: **попытка завершена BLOCKED на 07.1; feasibility не доказана; runtime не исправлен**.
Дата: 2026-10-04. План создан по запросу пользователя, не разрешает rollout.

## Активный короткий план — выполнить и вынести решение

### Итог исполнения текущей попытки — BLOCKED

Проверка 07.1 закончена по STOP-критерию; DONE 07.1 не достигнут. Это конечный
результат попытки, **не выполнение всех этапов и не исправление**.

Baseline: HEAD `669a991a`; полный tracked binary patch, архив untracked inputs
и manifest с hashes сохранены до diagnostic run в
`/tmp/opencode/next07-feasibility-baseline-20261004/`.
Архив локальный, не долговременный committed artifact. Runtime files не изменены.
Outputs и source hashes: `artifacts/next07/feasibility-audit-20261004.json`.

**Проверенный контракт и его граница:**

1. `condition → need`: local действует на связанный need; shared на все;
   unknown сохраняется без разрешающего target. Mandatory inputs/offsets —
   в scope table ниже. Их expected outputs не изменены.
2. `window → need`: routing IDs, score, соседство spans и два topic terms не
   устанавливают смысловую связь. Existing typed local witness может служить
   основанием только для поддержанного relation, с source/identity/dependency
   и visible-span checks. Unsupported relation остаётся unknown.
3. Этот консервативный контракт не удовлетворяет mandatory exception positive:
   existing grammar не представляет event-condition. Объявить его достаточным
   означало бы заранее заменить обязательный positive на unknown.

**Конкретный blocker, не утверждение общей невозможности:**

- `admission_grammar.py` не возвращает frame для
  `which exception is raised when an operation expires?`.
- Даже при вручную заданном local binding `_applicable_context` возвращает False
  для exception на body
  `When an operation expires, LeaseClient raises OperationExpiredError.`.
- На default и exception bodies matrix `[default,exception]` одинакова:
  `[True,False]`. True означает отсутствие constraint, **не relevance и не
  permission**. Это development diagnostic без source admission, не native test.
- Поэтому замены all-conditions loop недостаточно. Нужен общий event-condition
  witness/eligibility contract, отсутствующий в разрешённом scope-only trial.
  Compiler scope не может сам установить применимость source event clause.

**Inventory:** три известные local/shared/unknown questions — development;
два synthetic bodies — diagnostics, не acceptance. 80 frozen cases, 49 claim IDs
и прежние trial tests — regression, не unseen. Независимый набор не подготовлен
и не запускался; обобщение не заявляется.

**Изменённые файлы этого исполнения:** этот план, README,
`next07_feasibility_audit.py`, `test_next07_feasibility_audit.py` и новый JSON.
Diagnostic измеряет existing capabilities; не заменяет runtime decision и не
является candidate/rescue. Allowed runtime files не зафиксированы: достаточного
контракта нет, поэтому implementation STOP.

**Проверки:**

```sh
.venv/bin/python -m v2plan.next07_feasibility_audit v2plan/artifacts/next07/feasibility-audit-20261004.json
.venv/bin/pytest v2plan/test_next07_feasibility_audit.py -q
```

Audit пишет эксклюзивно: при повторе выбрать новый путь, не перезаписывать evidence.
Diagnostic tests: **2 PASS** — проверены blocker report и offsets, не recovery.

| Этап | Итог |
|---|---|
| 07.1 | BLOCKED: достаточная спецификация обоих bindings не получена |
| 07.2 | NOT_RUN: diagnostic не заменяет полную acceptance механизма |
| 07.3 | NOT_RUN: candidate не создан; прежний REJECTED не переименован |
| 07.4 | NOT_RUN: runtime/defaults/admission/selector не менялись |
| 07.5 | NOT_RUN: без candidate повтор replay/gates/full suite не обоснован |

Recovered/lost facts: новых native packets нет, recovery не доказана; baseline
факты этой попыткой не менялись. Guard regressions не измерялись end-to-end;
runtime patch отсутствует. Красные gates и failures 06 остаются открытыми.

**Один следующий шаг, только при отдельно разрешённом продолжении:** определить
общий event-condition source witness/eligibility contract: subject/event/polarity,
visible clause, clipping, неизвестные формы и независимая проверка. Не добавлять
regex под LeaseClient и не начинать новый trial автоматически. Если контракт
неприемлем в границах проекта, маршрут остаётся BLOCKED без обещания recovery.
Модель, новый parser и ослабление conditions этим итогом не разрешены.

Этот раздел — текущий маршрут. Разделы ниже сохраняют историю, результаты и
детальные checks; прежние указания «следующее действие» не запускают отдельные
циклы. Не создавать план 08 вместо завершения этого решения.

### Цель и честное обещание

Возвращать полезные найденные материалы с источниками и сохранёнными условиями
в пределах **800 tokens / 3 sources**, не обещая «это всё» или полный ответ.
«Показывать всё, что можно» означает полезный bounded context, а не все hits
и не обход guards. Полнота и применимость могут оставаться неизвестными.
В отчёте различать: доставлено / не подтверждено / не поместилось, если причина
известна. Не выдумывать причины отсутствия и не вводить автоматически новые API fields.

Неполнота ответа сама по себе не означает бесполезность context. При этом
identity, source/security, scope/version/freshness/snapshot/span/exact guards,
сохранение ограничений и запрет proof/edit authority обязательны. Unknown нельзя
выдавать за applicability. Проценты уверенности без калибровки запрещены.

### Текущий вывод, который нельзя забывать

- Per-need admission — **гипотеза**, не доказанно лучший алгоритм. Трудность —
  получить правильные связи «условие → часть» и «окно → часть», а не записать IDs.
- Preservation trial 6/7 не доказывает feasibility scope binding: он заведомо
  сохранял root constraints. Не повторять его как новый кандидат.
- Зависимость compiler → admission ожидаема. Она требует отдельных patch stages,
  но не доказывает невозможность compiler. Смешивать слои в одном trial нельзя;
  требовать полной native recovery от каждого промежуточного stage тоже нельзя.
- Надёжность исполнения заданных bindings и надёжность их извлечения из языка —
  разные результаты. Ручные bindings не доказывают native recovery.

### Порядок работы и критерии

| Этап | Что сделать | DONE / переход |
|---|---|---|
| **07.1 — заморозить эксперимент (сейчас)** | В этом плане записать поддерживаемые формы, outputs local/shared/unknown, основание window→need binding, список файлов и последовательность заменяемых обязанностей. Зафиксировать baseline commit+dirty patch, development/проверочный inventories и критерии до кода. | Есть конечная спецификация обоих bindings без case exceptions. Если её нет — BLOCKED с конкретным недостающим правилом; не писать очередной wrapper. |
| **07.2 — проверить механизм** | На явно размеченных bindings проверить применение local/shared/unknown и source guards, включая wrong subject/state и clipping. | Все обязательные controls проходят. Это только mechanism evidence, не NLP и не final packet. |
| **07.3 — один candidate извлечения** | Реализовать зафиксированные общие формы в существующем compiler; unsupported → unknown. Проверить обязательные positives и перенос на другие имена/отношения/формулировки, отрицания, quotes и shared/trailing restrictions. | Нет неверных разрешающих bindings; обязательные positives не заменены unknown; root obligations сохранены. На независимом наборе оценить также unknown/потери полезных фактов. После раскрытия ошибок правила под этот набор не подстраивать. |
| **07.4 — последовательная интеграция** | Только после 07.3: отдельные compiler/admission/selector patches, каждый с фиксированной заменяемой ответственностью и regression checks. Использовать existing capture/assessor. Новую границу admission/selector оформить до соответствующего patch, не считать её уже разрешённой этим планом. | Native root-only LeaseClient доставляет оба факта в обоих существующих параметрах; subject/условия сохранены. Если нужен rescue или другая policy сверх записанной — REJECTED, не расширять patch. |
| **07.5 — приёмка и конец** | Fresh paired 80-case replay; сохранить ранее подтверждённые 49 claim IDs и полезные partial facts; negative/guard/budget checks, focused tests, затем required gates и один полный offline suite. | Нет утраченных обязательных фактов, новых forbidden packets или failing nodes; ограничения и flags честные. Известные blockers 06 не превращаются в PASS. |

Для 07.1: baseline сейчас **6125 PASS / 93 FAIL / 10 SKIP**; 93 failures состоят
из 81 UNRESOLVED, 8 ENV_BLOCKED, 4 KEEP_FIX_RUNTIME. Это отправная точка, не цель
«оставить 93». Подтверждённый target defect должен закрыться по final bytes.
80 frozen cases и уже просмотренные fixtures — development/regression evidence,
не unseen. Если независимой проверки нет — явно BLOCKED для вывода об обобщении.

### Правила против бесконечной доработки

1. Один зафиксированный candidate, не серия новых grammar/thresholds после failures.
   Техническую ошибку harness исправить можно, сохранив исходный invalid run.
2. Перед каждым patch: обязанность → allowed files → ожидаемые positive/negative
   outcomes → команда проверки. Не менять чужой dirty baseline.
3. Не менять frozen labels, budgets, expectations, markers или required gates
   ради результата. Не добавлять fallback/rescue, library dictionaries и модель.
4. Не требовать доказанной полноты ответа от retrieval context; не выдавать
   отсутствие proof за разрешение игнорировать relevance или source restrictions.
5. После failing acceptance — записать контрпример и закончить verdict. Не
   компенсировать потерю одного факта приобретением другого или суммой PASS.
6. Не запускать уже выполненные проверки повторно без изменения или нового concern.
   При отсутствии модели/изоляции сохранить blocker; ручной ответ не model run.
7. Финал обязателен: **VALIDATED_LOCAL / REJECTED / BLOCKED**, выполненные этапы,
   recovered/lost facts, нарушения guards, список not_run и один следующий шаг.
   BLOCKED завершает попытку, но не исправление. Новая попытка — отдельное решение.

**Завершение 07:** вынесен обоснованный verdict по одной конечной попытке.
**Исправление LeaseClient:** только native delivery и сохранение guards/facts.
**Завершение 06:** отдельно закрыты решения по всем nodes и required acceptance;
локальный успех 07 не равен READY и не разрешает rollout.

### Исследования: основания и границы, не обещание результата

- [Break / QDMR (2020)](https://aclanthology.org/2020.tacl-1.13/): decomposition
  полезна; получение структуры исследуется как обучаемая задача, не доказательство
  универсального rule-based scope/binding.
- [Sufficient Context (2025), §3–5](https://arxiv.org/html/2411.06037v3): полезный
  context может быть неполным; autorater использует модель. Это не готовый
  model-free admission и не гарантия правильного ответа с источниками.
- [ALCE (2023)](https://aclanthology.org/2023.emnlp-main.398/): правильность ответа
  и качество подтверждения цитатами оцениваются отдельно.
- [CheckList (2020)](https://aclanthology.org/2020.acl-main.442/): behavioral checks
  выявляют ошибки за общей accuracy; это метод проверки, не доказательство полноты.

В этих источниках не установлено превосходство нашего per-need candidate.
Исследование обосновывает конечную проверку гипотезы, не бесконечное расширение parser.

---

## Предыдущая детализация и история (не отдельная очередь исполнения)

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

### Зафиксированное правило: источники вместо некалиброванной confidence

По согласованию с пользователем: указывать проверяемые источники, сохранять
условия/subject и явно различать происхождение, применимость и полноту ответа.
Неизвестная применимость не становится подтверждённой; отсутствие условия
не означает ни соответствие, ни противоречие. Вывод требует evidence.

Проценты уверенности запрещены без определённого оцениваемого события и
независимой held-out калибровки. Lexical score, match ratio и retrieval coverage
не являются вероятностью правильности. Измеренные доли покрытия с явным
знаменателем можно показывать только как coverage, не как confidence.
False proof/edit flags также не устанавливают применимость отдельной цитаты.

Постоянное правило: [AGENTS.md](AGENTS.md#источники-и-неопределённость-обязательное-правило).
Это не implementation semantic classifier, не снятие blockers B3/C и не
разрешение на новую schema, runtime-модель или ослабление guards.

## 1. Правила исполнения для модели

### Согласование scope trial

Пользователь явно выбрал **«Узкое расширение»**. Это отдельное разрешение после
отклонённого preservation trial. Оно снимает запрет на новые scope-правила
внутри существующего compiler только в границах ниже; прежние результаты сохраняются.

**Ответственность:** определение того, к каким частям исходного вопроса относится
условие. Заменить неразличённое распространение root constraint на все части
явным local/shared/unknown binding. Не добавлять параллельную разрешающую ветку.

**Разрешено:** расширить существующие compiler-правила и внутренние структуры
для condition span, target part IDs и scope verdict. Точные поля, формы grammar
и affected callers фиксируются до кода. Scope verdict описывает вопрос, а не
применимость документа; даже известный scope не повышает interpretation до
`supported` и не даёт proof/coverage/edit permission.

**Не разрешено:** новый parser, library/relation exceptions, словари, fallback,
threshold tuning, изменение retrieval/admission/selector, guards, budgets,
public schema, frozen expectations или переключение production/defaults.
Неизвестный scope не даёт разрешения снять constraint с какого-либо need.

Порядок следующего trial:

1. Составить таблицу вход → точные part/condition spans → local/shared/unknown
   → target IDs. Зафиксировать исчерпывающую поддержанную форму каждого правила,
   не список названий клиентов. Остальные формы — unknown.
2. Обязательные acceptance examples:
   - LeaseClient default + exception when operation expires: два parts;
     expiration относится к exception, default не получает это условие.
   - `When preview is disabled, what is RelayClient default timeout and which
     exception is raised?`: shared condition на обе части.
   - Тот же compound с `, only for administrators?` в конце: unknown scope,
     условие сохранено; default не становится безусловно разрешённым.
3. До реализации добавить отрицательные controls: вложенные/несколько условий,
   перенос prefix в trailing position, отрицание, разделители внутри quotes,
   другой subject второй части, exact identities и reference mismatch.
   Unknown — допустимый результат неподдержанной формы, но не замена ожидаемого
   local/shared в обязательных positives. Не выводить scope только из близости spans.
4. Проверить consumers: могут ли они безопасно сохранить unknown без изменений
   admission/selector. Если необходим второй policy-слой — STOP, описать зависимость.
   Не выдавать новые поля, которые старый consumer игнорирует, за исправление.
5. Выполнить один isolated compiler candidate поверх зафиксированного baseline.
   Проверить regression tests, существующие compiler/condition controls и
   отсутствие потери root obligations/точных offsets. Нет нового input — нет
   основания повторять отклонённый trial с подогнанными правилами.

**DONE этого trial:** обязательные local/shared/unknown examples и negative
controls проходят; constraints/subject/exact identities не потеряны; новые
scope assertions не дают source applicability или support; изменён один слой.
Это `COMPILER_VALIDATED_LOCAL`, не `FIX_VALIDATED_LOCAL`.

**STOP/REJECTED:** ошибка области действия, новое разрешение из unknown, потеря
guard/constraint, исключение под fixture или необходимость менять второй слой.
После compiler приёмки native LeaseClient packet проверяется отдельно. Admission
и selector требуют собственных trial boundaries; rollout не разрешён.

Следующее действие: зафиксировать таблицу форм/outputs и consumer compatibility,
затем failing regression tests. Исследование и implementation пока NOT_RUN.

### Общие правила

#### Scope contract table и consumer compatibility — выполнено до candidate

Все spans ниже `[start,end)` в неизменённом original question. IDs `part-1/2`
обозначают исходные части, не независимые proof obligations. Предлагаемый
внутренний binding: `condition_span`, `scope=local|shared|unknown`, `target_need_ids`.
Для unknown список targets отсутствует (не пустой список «ни к чему не относится»);
legacy constraint сохраняется консервативно. Это спецификация, не новые runtime fields.

| Input form / пример | Scope / targets | Обязательные ограничения |
|---|---|---|
| `What is LeaseClient default timeout duration for requests and which exception is raised when an operation expires?` | local → part-2; condition `[88,114)` | part-1 `[0,57)`, part-2 `[62,114)`; exact subject сохранён; binding не доказывает, какую exception возвращает источник |
| `When preview is disabled, what is RelayClient default timeout and which exception is raised?` | shared → обе части; prefix `[0,25)` | Условие должно быть доступно обеим частям; context не превращается в proof |
| `What is RelayClient default timeout and which exception is raised, only for administrators?` | unknown; restriction `[67,91)` | Не объявлять local только потому, что restriction находится в конце второй части; не снимать constraint с default |
| Две явные части без condition cues | Без condition binding | Сохранить parts/subject/context и root exact obligations; interpretation остаётся unresolved |
| Condition marker/separator внутри backticks, quotes или link | Не condition / не новая boundary | Existing protected-span handling; значимые bytes остаются частью exact identities |
| Вложенные/несколько условий; отрицание; prefix, перенесённый в trailing position; другой subject | unknown до явно зафиксированного общего grammar rule | Не выводить local/shared из близости, совпадения subject, очередности spans или retrieval score |

Эта таблица фиксирует expected examples, **но не завершённую grammar**: перед
candidate требуется точная общая production, различающая local event clause от
ambiguous trailing modifier без library-specific словаря. Пример не означает
разрешение special-case `LeaseClient`, `expiration` или relation `exception`.

Consumer audit (текущий код, без runtime подмен):

| Consumer | Фактическое использование | Совместимость |
|---|---|---|
| `source_reference_evidence.py:62–66` | Сохраняет compiled contracts для prepared source routing | Producer может хранить binding; это не enforcement |
| `evidence_set_validation.py:109+` | Проверяет source/span/dependency integrity; proposed need IDs — routing hints | Не устанавливает condition scope или applicability |
| `need_context_disposition.py:50–76` | Смотрит наличие constraints, затем заново парсит текст отдельного need; общего prefix в `need.context` для condition frame не использует | Shared condition в context не будет автоматически понят; неизвестная форма остаётся blocked |
| `need_context_projection.py:141–149` | Вычисляет disposition для каждого need и допускает окно при любом non-blocked need | Per-need route существует; новые scope targets сами по себе не потребляются |
| `read_context_admission.py:105–107` | Проверяет **каждый** constrained need против **каждого** body; один отказ запрещает всё окно | **Несовместим с целью local scope:** exception constraint продолжает запрещать independent default |

Проверка на предполагаемом compiler output: у default пустые constraints,
у exception `[88,114)`, body `The default timeout is 17 seconds.`.
Existing `_applicable_context` возвращает True для default, False для exception.
Actual read consumer применяет второй verdict к тому же body и всё равно
возвращает `condition_support_unavailable`. Результат probe сохранён в
`artifacts/next07/scope-consumer-compatibility-20261004.json`.

**COMPATIBILITY BLOCKED / STOP перед новым candidate.** Для native эффекта
нужна отдельная ответственность admission: выбирать, какой need относится
к окну, и проверять только его constraints, не ослабляя shared/unknown veto.
Один compiler-only patch не может исправить этот consumer. Изменять его в этом
trial запрещено. Не добавляем игнорируемые поля ради green syntax tests.

Новый candidate и новые grammar regression tests **NOT_RUN**: остановка по
пункту 4 согласованной границы до реализации. Предыдущие красные tests и
REJECTED preservation candidate сохранены. Следующее решение — согласовать
отдельный per-need admission consumer contract и последовательность его trial,
либо оставить compiler исследованием без заявления native recovery.

Уточнение по согласованной последовательной работе: допускаются отдельные
compiler → admission → selector trials, каждый с собственным решением C и
проверками. Необходимость следующего слоя не делает промежуточный trial полным
исправлением и не разрешает смешивать слои в одном patch. Новый trial не
начинается автоматически после regression или неопределённого scope.

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

### Compiler-only trial: сохранение существующих RetrievalNeed

Заменяемая ответственность: сворачивание нескольких существующих retrieval
parts в один unresolved `requested_part` при enrichment. Остальные compiler
ветки и все runtime consumers неизменны. Candidate исследуется только через
отдельную функцию в `next07_compiler_trial.py`; defaults не переключаются.

Проверяемое общее правило: сохранить существующие части/subject/context/offsets,
root exact obligations и unresolved interpretation. Existing root constraints
сохранять консервативно, пока существующий parser не подтвердил их область.
Не выводить scope из порядка слов и не вводить новый grammar/condition classifier.

Проверка: `test_next07_compiler_trial.py` — локальное expiration, global prefix,
ambiguous trailing restriction, exact identities, quotation shielding и
reference mismatch. Обязательный acceptance: expiration не переносится на default.
Если candidate его не выполняет, trial отклоняется, а не ослабляет guard.

Allowed files: этот план, `next07_compiler_trial.py`,
`test_next07_compiler_trial.py`, `artifacts/next07/`, строка статуса в README.
Production compiler/admission/retrieval/selector/budgets не изменяются.
Это trial формирования контрактов, не проверка native recovery.

**Результат:** native **5 PASS / 2 FAIL**, isolated candidate **6 PASS / 1 FAIL**
(общий запуск 11 PASS / 3 FAIL). Baseline не сохраняет два retrieval parts;
candidate сохраняет parts, subjects, original offsets и exact obligations,
оставляя interpretation unresolved. Global/ambiguous restrictions, quoted
separator и mismatch controls проходят в обоих arms. Это syntax controls,
не полная приёмка source/security guards и не native delivery.

Обязательный локальный condition test у candidate падает: `default.constraint_spans`
всё ещё содержит `when an operation expires?`. Existing `RetrievalNeed` даёт
границы частей и эвристический context, но не certificate области действия
условия; `NeedContract` имеет constraint spans без отдельного scope verdict.
Копировать constraints всем частям безопаснее снятия veto, но не выполняет цель.
Раздать их только по пересечению spans — новая неподтверждённая scope-политика:
она могла бы снять общий trailing restriction с первой части.

**Verdict: REJECTED для этого candidate; D/E native acceptance NOT_RUN.**
Tests не ослаблены, candidate не подключён к consumers/defaults. Сохранён как
отрицательный research результат, не production fix. Artifacts:
`artifacts/next07/compiler-preservation-20261004/` — XML, обоих arms contracts,
summary с hashes и command. Текущие 93 offline failures этим не закрыты.

**STOP:** до следующего trial требуется основание для binding condition scope,
которого в existing parser нет. Ни span proximity, ни порядковое положение
условия, ни confidence не заменяют его. Переход к admission/selector сейчас
маскировал бы compiler failure, поэтому автоматически не выполняется.

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

### Выполнение 2026-10-04 после коммита плана

- План закоммичен первым: `c49e5221`; baseline включает сохранённый tracked dirty
  patch и hashes untracked inputs. Остальные изменения пользователя не отменены.
- Artifacts: `artifacts/next07/20261004-baseline-c49e5221/`.
- **A DONE:** fresh focused run **74 PASS / 2 FAIL**, оба LeaseClient parameters
  потеряли timeout; packet содержит overview. XML: `baseline-focused.xml`.
  Syntax diagnostic подтверждён также actual prepared root plans, не только
  пустым catalog: два RetrievalNeed → один unresolved requested_part с condition.
- **B1/B2 observed:** 15 calls, 9 development cases; для двух LeaseClient cases
  выполнены все четыре arms. В обоих factual sources точные heading-inclusive и
  body-only окна получают `condition_support_unavailable`; при bypass condition
  получают `no_local_topic_witness`. При обходе обоих veto или сохранении всех
  chunks на rerank они достигают projector и получают candidate rejection
  **`no_visible_qualification`**. Они не достигают обычной selection. Overview
  accepted/replaced; read fallback не вызывается при непустом sources (code-derived).
  Следовательно, финальный барьер здесь не `no_new_direction` из исследования 02.
- **B3 observed:** global-condition доставляет disabled **и enabled** цитаты;
  wrong-state-only доставляет enabled; missing-state доставляет безусловный default;
  unknown administrators scope также доставляет безусловный default. Во всех
  случаях proof/edit flags false. Restriction-tail final сохраняет `Only when
  preview is disabled.`. Missing-error и foreign-subject LeaseClient packets пусты.
  Все 15 captures проходят existing projection validator на 800/3.
- Это не доказательство condition safety: validator проверяет другой контракт.
  Возврат enabled quote с целым условием может быть contrasting read context,
  но его допустимость не установлена. Не называем его applicable/answer proof.
- **B не полностью DONE:** новые clipping/exact/version/source mutation controls
  для B3 ещё не выполнены; existing source/snapshot/request/unsafe controls
  присутствуют в passing A2, но не заменяют будущую candidate приёмку.
- Первый `trace/` run технически не собрал actual plans: dataclass chunks до
  rerank не содержат `_reference_root_plan`. Observer исправлен на prepared read
  candidates; повтор `trace-with-plans/` сохранён отдельно. Первый run не удалён,
  его пустые `actual_plans` не используются для conclusions о source binding.
- **C NOT_SELECTED / BLOCKED:** compiler-only оставляет lexical и projection
  barriers; admission-only оставляет projection qualification; selector-only
  не получает законно admitted factual windows на native prefit. Общей безопасной
  replacement rule сейчас нет. Mechanical refactor не выбран вместо recovery.
- **D/E NOT_RUN:** runtime/defaults, expectations и frozen labels не менялись;
  full suite и 80-case candidate acceptance не запускались без candidate.
- **Verdict: IMPLEMENTATION_BLOCKED; анализ B частичный, не ANALYSIS_COMPLETE.**
  LeaseClient fixed: **no**. Plan-06 blockers остаются открытыми.
- **STOP / следующий один вопрос:** разрешается ли возвращать attributed read
  context с неприменимым либо неподтверждённым условием (например enabled quote
  на disabled request / unconditional default на administrators request), если
  условия источника сохранены, applicability не заявляется и proof/edit false?
  Если да, требуется отдельно определить, как packet сообщает это ограничение;
  текущие false flags сами по себе этого не обеспечивают. Если нет, такой veto
  должен действовать на все delivery routes, а не только на read fallback.
  Ни один вариант не даёт автоматического разрешения multi-layer patch.
