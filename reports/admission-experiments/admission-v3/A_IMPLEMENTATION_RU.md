# A: минимальная implementation V3

2026-10-12. Основание: `CONTRACT_DECISION_RU.md` зафиксирован координатором до patch/inference. Реализован только узкий opt-in scalar-label fallback; это **не runtime PASS и не production recommendation**.

## Изменённые файлы и точный delta

1. `docmancer/docs/domain/original_body_discovery.py`:
   - В существующем live `_BodyRead` один раз на original public invocation захватываются только `policy_candidates_v1` либо `scalar_label_candidates_v3` из host env. Не добавлены wire аргументы, receipt grants, источники или I/O.
   - `policy_candidate_admission_active()` признаёт оба режима для наследования B1 machinery и существующего selector. Новый `scalar_label_candidate_admission_active()` признаёт только точный V3 mode; после закрытия owning handler оба недействительны.
   - Scope/lookup/module/library/maintenance/context-format exclusions, native identity/hash/catalog/member/window receipts и их teardown неизменны.
2. `docmancer/docs/domain/ordinary_body_context.py`:
   - Receipt/structural-owner/unresolved-name/body-block eligibility вынесены в `_source_valid_body_blocks`. `_policy_valid_body_blocks` поверх него выполняет прежнее exact subset всех digit-bearing `_literal_terms` в одном body block.
   - Ordinary phrase/technical route и первоначальный B1 candidate route используют именно прежний numeric filter. Если B1 нашёл substantive block, возвращается прежний `policy_valid_original_candidate_v1` witness. V3 fallback вызывается **только после отсутствия такого B1 candidate**; для old mode/default он сразу закрыт.
   - `_scalar_label_pairs` сканирует максимальные `\S+` токены. Scalar целиком соответствует ASCII unsigned decimal `[0-9]+(?:[.,][0-9]+)?`. Decimal comma атомарна; `7-9`, `v1`, `1.2.3`, namespace/path/identifier, exponent, знак, attached punctuation/скобки не могут предоставить часть своего токена как scalar.
   - Следующий whitespace-separated token должен быть целиком буквенным label с максимум одним конечным sentence punctuation `. ! ? ; : ,`. Alphabetic проверяется также `isalpha`; whole label сравнивается casefold. Никакого словаря единиц или query rewrite. Spaced соседние operator/sign/range tokens консервативно закрывают pair, включая Unicode signs/comparisons.
   - Fallback query eligibility: непустой set **всех** `\S+` токенов original question с `char.isdigit()` должен в точности совпадать с полными scalar spans валидных pairs. Неизвестная цифра, повторная digit occurrence без label, range/technical token или trailing bare number закрывает новый fallback целиком. ASCII — сознательно узкая грамматика; другие цифровые записи не угадываются.
   - Source eligibility: в одном существующем masked structural body block нужна одна валидная scalar-label pair с literal label из query. Не требуется каждый query value/label в каждом source. Source scalar не обязан равняться query scalar; сравнения и единицы семантически не выводятся.
   - После pre-inference исправления **A-SOURCE-EDGE-01** source syntax проверяется по **полному immutable original raw document**, а не по `raw[source_offset:end]`: `_scalar_label_pairs(raw)` учитывает полные scalar/label tokens и соседние maximal sign/operator tokens с обеих сторон, даже за краем разрешённого окна. Masked-block pair переводится в absolute coordinates и должна полностью совпасть со всеми fields соответствующей full-raw pair. Недоступный/non-string raw или отсутствие такого совпадения закрывает fallback. Прежние char-whitespace guards удалены как недостаточная замена полного syntax context.
   - Отдельно обязательно `0 <= source_offset <= pair_start < pair_end <= block_end <= len(raw)`; complete pair substring должен равняться original raw bytes. Полный raw используется только для syntax veto/подтверждения контекста, не для заимствования пары/цифры/label извне allowed body block. Delivered block/witness span и native discovery operand не расширяются. Equality masked/full-raw fields не позволяет masking создавать новые technical/числовые границы или пропускать содержимое внутри pair.
   - Возвращается первый подходящий source pair и первое query occurrence этого label, не Cartesian matrix и не глобальный cross-document state. Все валидные query pairs также сохранены отдельно для аудита полного query digit coverage.

Прежние V1/V2 изменения оставлены на месте. Не изменены retrieval, qualification, selector, ranking, projection, validators, DTO/schema, tests, eval drivers, вопросы, corpus и oracle. Новый holdout не читался.

## Witness / metadata contract

Новый witness:

- `kind = scalar_label_original_candidate_v3`;
- `relevance_unassessed = True`, `numeric_condition_unassessed = True`;
- `text` — original raw block slice; `char_start/end` и `block_char_start/end` — absolute document coordinates;
- прежний `native_discovery_binding_sha256`;
- `query_scalar_label_pairs` — полный список query pairs с exact `text`, `scalar`, `label`, `char_start/end`, `scalar_char_start/end`, `label_char_start/end`; координаты относительно неизменного original question;
- `scalar_label_pairs = [{query: ..., source: ...}]` — одна supporting local pair; все source coordinate fields абсолютны относительно original raw document. Конечная sentence punctuation не входит в pair text/label span.

По прочитанному shared API blocker на metadata **не найден**: `literal_context_admission.py` помещает returned witness в `body_witnesses`, использует его generic `kind` как reason и сохраняет `coverage_credit=False`. Tagging/ranking/projection повторно вызывают тот же admission на текущих operands. По grep в product нет closed enumeration этих witness kinds/body fields. Это статическое заключение о пути, **не доказательство public delivery или wire-публикации всех private pair fields**. Public snippet/schema прежние; diagnostic witness не выдаётся за отдельный authoritative source DTO.

Canonical qualifier/hard-exact/body-window/source-policy gates и downstream operational veto не переписаны. Новые fields не дают qualified IDs, coverage, supported answer или edit permission. Никакой обработки incoming witness как доверенного grant не добавлено.

## Риски, ограничения и сохраняемые negatives

- Scalar-label — синтаксис, не semantic unit recognizer. Одиночная запись `1.4` без technical оболочки может означать decimal или version; parser не умеет выводить смысл bare number/label. Composed versions/paths/IDs отвергаются синтаксически, но самостоятельные числа с буквенными labels остаются unassessed. Совпадающий label разных показателей/условий не даёт entailment.
- Maximal whitespace grammar намеренно консервативна: decorated scalar, отсутствие пробела, multiple punctuation, некоторые Unicode/научные числовые записи и соседняя punctuation/operator prose могут дать false negative. Нет эвристического исправления после наблюдения результата.
- Full-document context check консервативно видит ближайшие whitespace tokens даже из соседнего структурного блока: оператор там может отклонить пару, хотя тематически к ней не относится. Это допустимый false negative, не повод ограничить context обратно acquired window. Добавлен один полный raw scan/index на invocation нового candidate fallback; стоимость/память не измерены, cache не добавлен. Синтаксический соседний-token veto не является полной семантической грамматикой выражений.
- Numeric fallback не допускает безчисловые cargo/refund blocks. Полный multi-document recall заранее NOT_SOLVED; project membership/heading/folder не создают связь между facets.
- Сохраняются прежние strict empty-source expectations. Nonempty unrelated candidate остаётся CURRENT_CONTRACT FAIL независимо от host refusal. У V3 сохраняется B1 unassessed lane и его известный relevance риск; fallback с incidental common label тоже не гарантирует strict emptiness.
- Старые priority `7`/`7-9` запросы не получают новый fallback: scalar без следующего whole label / composed range и источник без numeric pair не создают его. Это статическое ожидание, НЕ новый PASS. Если legacy B1/ordinary route допускает другие complete numeric requests, это не новое ослабление V3 fallback.
- Owner/unresolved-name/hard-exact/source-policy сохраняются; Q31 HumanEval/LeetCode не исправлялся. Missing numeric identity не превращается в answer-supported condition.

## Проверки и handoff

Выполнены только source text reads/grep и patch; исходная read-only git status была в этапе контракта. Runtime/tests/import/compile/AST/models/host не запускались. Новый V3 holdout/oracle не читался. Нет claims об actual restored pool, final source bytes, source-policy regression, full default parity или числовых ответах.

Product ownership соблюдён: изменены только два назначенных domain файла. A reports находятся только в V3 evidence. Следующий шаг — независимый статический review и только отдельно разрешённый public integration эксперимент с unchanged questions/oracle; если shared validation действительно блокирует новый witness, вернуть blocker, не обходить veto.

### Pre-inference fix A-SOURCE-EDGE-01

По запросу координатора прочитан `review/PATCH_PREFLIGHT_RU.md`; исправлены **только** `ordinary_body_context.py` и этот отчёт. `original_body_discovery.py`, old B1/default numeric/ordinary parsers, query parser grammar, metadata schema, downstream validators и frozen inputs не изменены. Frozen questions/oracle не читались в этом исправлении. Sign/operator за левым либо правым краем raw-window теперь может отвергнуть local pair через отсутствие exact full-raw match. Ни один pair вне acquired masked body block не может дать witness. Полный raw уже является canonical immutable operand; новый source read/expansion/network/global cross-document binding не добавлены.

Это source-level pre-inference исправление, не исполненный negative scenario/интеграционный цикл и не окончательное закрытие C verdict. Runtime/tests/import/compile/AST/models/host не запускались; identities/patch freeze должен обновить координатор перед независимым повторным статическим review.
