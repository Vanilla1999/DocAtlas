# PR211: девять critical normative failures — контракт и предложения successors

Read-only разбор exact `04ff1dda57efb5236d7b3577d4e2736b2820df5b`.
Это предложение для решения о scope, не разрешение на миграцию и не acceptance.
Repository files, tests, gold, floors, gates и selectors не изменены; runtime,
imports, новые CI runs и retrieval pilots не выполнялись.

Уже сохранённый critical baseline содержит 28 cases: 19 PASS / 9 FAIL.
Девять FAIL принадлежат одному parameterized node:
`tests/docs/test_normative_language.py::test_normative_modality_is_deterministic_and_preserves_legacy_cases`.
Их единственный assert на строке 44 требует старый `required`/`forbidden`,
тогда как текущий adapter возвращает `None`. Остальные 17 параметров этого node
и два независимых Task33/host-turn-limit tests PASS в том baseline.
Ни один из трёх critical mutants тогда не запускался.

## Установленный конфликт, а не подгонка под actual

1. `docmancer/docs/domain/normative_language.py:79–85` прямо определяет adapter:
   source prose не устанавливает policy modality; `classify_normative_modality`
   безусловно возвращает `None`, `has_normative_language` поэтому false.
   Это не случайный regression конкретного словаря. В production tree нет
   других вызовов classifier, кроме самого compatibility wrapper.
2. Исторический implementation report
   `v2plan/stage3/pr211-context-admission-checkpoint-2026-10-06/READ_PACKET_RESIDUAL_DICTIONARY_EXIT_RU.md:16–23`
   явно фиксирует R3: modality unknown, zero fact/validation credit из prose,
   но Python declaration grammar сохранена. Его hash production normative module
   совпадает с current source: `de87153f…`.
3. `v2plan/action-packet-v4/CONTRACT.md:7–39` требует непустые sources для data,
   точные полные text/hash/span/identity, untrusted data и edit_ready=false;
   новые obligations не выводятся из prose. Без explicit content obligations
   отсутствие content assignment сохраняет partial. Amendment 7, строки 205–222,
   разрешал API migration eval, оставляя historical gold/expectations неизменными
   и unsupported normative/workflow requirements fail-closed.
4. `V4_PRODUCT_DECISIONS_RU.md:23–41` требует сохранить факты, условия,
   ограничения и исключения, но передаёт semantic sufficiency/действия host.
   `CURRENT_WAVE_DECISIONS_RU.md:19–25,46–51` сохраняет source binding,
   consent/no automatic edit authority и остальные gold/gates.
   `after-merge/RETRIEVAL_DEFERRED_ANALYSIS_RU.md:7–13` прямо запрещает
   автоматическую смену gold/thresholds/gates и retrieval fixes.

Итак, **старый вывод policy modality из этих девяти строк явно retired**.
Однако обычная замена всех expected на `None` не сохраняет остальные полезные
свойства старой проверки: отличать prose от Python, не терять отрицание,
условие/временную границу, и действительно доставлять source bytes.
Uniform `None` ничего из этого не доказывает. Текстовые свойства нужно перенести
в конкретные положительные и отрицательные controls, а изменение acceptance
сначала явно согласовать. Нельзя назвать новое поведение эквивалентной реализацией
старого normative classifier: это сознательная замена проверяемого контракта.

## Per-case mapping всех девяти исходных параметров

Во всех строках ниже предлагается общий **P/N protocol**, описанный далее.
Исходное text и legacy expected остаются frozen fixture data/ID labels;
ни словарь, ни классификация смысла в production не восстанавливаются.
Каждый exact text целиком должен сохраниться как source data. Negative text
ниже — контролируемая порча только копии уже построенного packet, не новое gold
и не новый question/lookup для retrieval.

| № | Исходный text / старый expected | Что теряется при одном `None` | Конкретный successor positive + negative |
| --- | --- | --- | --- |
| 1 | `Offline fallback cannot bypass the gate.` → `forbidden` | Сохранение отрицания и локального subject; uniform unknown совместим с выдачей противоположной цитаты или пустой выдачей. | P: полный exact source с `cannot bypass`, без policy grant. N: подменить только `cannot` на `can`, пересчитать self hash/estimate и потребовать rejection относительно исходного evidence. |
| 2 | `The worker may not continue without evidence.` → `forbidden` | Отрицание вместе с условием `without evidence`; keyword `evidence` не заменяет всё условие. | P: вся строка, включая `may not` и `without evidence`. N: `may not` → `may` при прежнем evidence; bound validator обязан отвергнуть. |
| 3 | `Don't bypass PermissionService.` → `forbidden` | Апостроф/отрицательная imperative форма и точное имя PermissionService; source text нельзя превращать в runnable instruction. | P: полная исходная цитата, untrusted/no edit. N: `Don't` → `Do` с новым self hash, но прежним bound evidence; rejection. Дополнительно policy/workflow promotion отвергается. |
| 4 | `PermissionDecision.deferFollowUp is reserved for post-entry review.` → `required` | Временная граница `post-entry` и exact qualified symbol; old required label и сам по себе не доказывал правильную область. | P: полный symbol и `post-entry review` в exact bytes. N: `post-entry` → `pre-entry`; валидатор source binding отвергает даже self-consistent изменённый text/hash. |
| 5 | `The invariant preserves immediate denial.` → `required` | Условие immediate, которое нельзя заменить отложенным результатом. | P: весь текст и hash, без inferred invariant array. N: `immediate` → `deferred`; rejection относительно исходного evidence. |
| 6 | `From configuration, retries are required.` → `required` | Нельзя отбросить prose как Python по начальному From или стереть obligation wording при доставке. | P: bounded declaration grammar возвращает пустой line set; source содержит полный `From configuration, retries are required.`. N: заменить `required` на `optional` в packet; rejection. |
| 7 | `from configuration, retries are required.` → `required` | Lowercase `from` не делает текст синтаксически корректным import; сохраняется регистр и запятая исходной строки. | P: отдельный case, grammar empty и byte-exact lowercase source. N: `required` → `optional` с прежним evidence; rejection. Не объединять с №6 через casefold/dedup. |
| 8 | `From configuration import rules are required.` → `required` | Наличие `From`/`import` ещё не Python declaration; строка о policy не должна исчезнуть при prefix filtering. | P: grammar empty, полный исходный source. N: `required` → `optional`; bound rejection. Не выводить policy role из слова rules. |
| 9 | `Import policy is required.` → `required` | Начальный Import — не грамматическое import statement; нельзя потерять prose или придать ей executable authority. | P: grammar empty, полная строка. N: `required` → `optional`; bound rejection, плюс no-authority controls. |

Для №1–5 также ожидается empty Python declaration line set: это source-grounded
синтаксическая проверка, не новый semantic classifier. Все девять строк не являются
единственной корректной Python declaration по stdlib AST. Эта проверка сделана
только статически; repository grammar/runtime не запускался.

## Общий P/N protocol, который сохраняет самопроверяемое свойство

Предлагаемый test successor использует малый authored in-memory evidence fixture
по существующему примеру `tests/test_dictionary_exit_read_packet_residuals.py:36–73`:
literal docs path, stable child + parent identity, display_text=исходный text,
exact UTF-8 display hash, действительные char/line spans. Это тест producer и
validator после передачи fixture evidence, без SQLite acquisition, расширения
retrieval, providers и исправления deferred relevance/admission.

Положительный контроль для каждой исходной строки:

1. Current compatibility modality остаётся unknown; Python grammar проверяется
   отдельной функцией `python_declaration_line_indexes`, не по результату modality.
2. Реальный `build_action_packet` получает evidence и исходную строку как question,
   без public_requirements, mutation/authority grants, invented proof_role или
   aliases. При необходимости retained-data path доказывается сначала тем же
   selector, а не ручной сборкой packet.
3. Обязательны `result=data`, непустые sources и **полное exact equality** source
   text с исходной строкой; SHA256, path/stable identity и supplied span также
   связываются с fixture. Нельзя удовлетворить guard пустым failure/unknown.
4. `instruction_trust=untrusted_data`, `edit_ready=False`, нет legacy
   required_invariants/forbidden_changes/validation и нет новых policy assignments
   из текста. Без explicit content assignment ожидается data/partial с текущим
   missing-content-assignment reason; `complete` не выдумывается для зелёного test.
5. Реальный `validate_action_packet(packet, evidence_items=[original]) == []`.
   Если нужно доказать model-visible transport, вызывается настоящий projector
   и его snapshot validator — это отдельный более широкий successor,
   а не утверждение, что unit packet test уже проверил MCP delivery.

Отрицательные controls для того же валидного, непустого positive:

- **Fidelity:** per-case порча из таблицы. Пересчитать self content hash, supplied
  char_end по новой длине и packet estimate, чтобы rejection нельзя было приписать
  только checksum/span/estimate.
  Проверить именно ошибку `source differs from bound retrieval window` через
  validator с исходным evidence. Это механическая сохранность source текста,
  а не попытка научить DocAtlas смыслу противоположного предложения.
- **Authority:** копия packet с trust promotion должна получить конкретную
  schema/guard ошибку для `instruction_trust`; отдельная копия с `edit_ready=True`
  — ошибку для edit_ready. Recompute estimate устраняет случайное срабатывание
  нерелевантного budget check.
- **Policy laundering:** добавленный legacy required_invariants/forbidden_changes
  или runnable validation отвергается strict schema; не использовать общий
  `assert errors` при повреждении нескольких независимых полей.
- **Python/prose distinction:** существующие 15 single-line Python declaration
  cases требуют `{0}`, девять prose выше и два других nondeclaration cases
  требуют empty set. Все 26 fixtures сохраняются; существующие parenthesized
  import controls остаются полезной отдельной coverage.

Source grounding этого protocol: `_action_packet_part03.py:24–35,70–143`
формирует whole display text и untrusted sources; `_action_packet_part04.py:146–219`
проверяет schema/hash/span и exact соответствие source bound retrieval candidate.
`_action_packet_shared.py:83–138` фиксирует untrusted/false и strict allowed fields.
Уже существующие `test_forged_source_rejected`,
`test_unknown_fields_and_non_authorization`,
`test_sdk_packet_consumer_rejects_forged_promotions` показывают актуальную границу.

Это proposal, а не заявленный PASS этих девяти новых producer cases. Если
неизменённый selector не допустит какой-либо fixture, нельзя скрыто добавлять
provenance/authority flags, менять question или lookup, ослаблять admission
либо объявлять пустой failure успешным successor. Такая граница возвращается
на review отдельно; deferred retrieval остаётся вне scope.

## Второй blocker: critical mutant уже не соответствует source

`scripts/run_critical_mutation_gate.py:31–37` требует unique anchor
`if is_python_declaration(text):` в normative_language.py. **Exact count сейчас 0.**
`_apply_mutant:110–120` при count != 1 завершится ошибкой. Даже если девять
expected механически заменить на None, gate после зелёного baseline остановится
на отсутствии anchor; это не killed mutant и не PASS.

Исторический mutant проверял, что code declarations не превращаются в normative
facts после отключения classifier guard. В нынешнем uniform-unknown adapter
самой ветки больше нет. Нельзя восстановить запрещённый prose classifier только
для оживления старого anchor и нельзя просто убрать mutant/снизить их количество.

Для отдельного явно согласованного gate migration требуется выбрать актуальное
свойство и показать non-NOOP + guard-specific kill:

- Grammar successor: unique реальная строка
  `declaration_lines.update(range(line_index, end_index + 1))` →
  `declaration_lines.update(())` убирает recognition корректных declarations;
  positive `{0}` controls должны убить mutation. Обратное чрезмерное признание
  всех строк declarations должно ловиться empty-set prose controls. Это не
  эквивалент старого semantic classifier, а сохраняемое техническое свойство.
- No-authority successor: scoped изменение тела compatibility adapter
  `return None` на `return "required"` должно провалить unknown guards, а
  producer trust/edit promotion — соответствующие P/N guards. Такое изменение
  должно быть привязано к exact function, не broad строковой замене всех returns.
- Fidelity successor: изменение whole-window source delivery обязано провалить
  exact text/hash/binding positive, а не рассчитывать на exception/collection error.

Как эти свойства распределить между существующим critical mutant и дополнительными
проверками — отдельное решение о test/gate контракте с independent review.
Baseline обязан быть зелёным на настоящем final SHA; каждый mutant должен менять
реально используемый source, завершаться assertion failure без collection/errors,
сохранять import-origin isolation. Остальные два current critical mutants и
их Task33/turn-limit properties не требуют изменений из этого разбора.

## Нужное scope decision

Разрешить или не разрешить **явную миграцию retired normative modality acceptance**
в source-data fidelity + no implicit authority + сохранённую Python grammar,
с frozen исходными 26 fixture texts/IDs и guard-specific mutation replacement.
Это не retrieval fix и не автоматическое снижение historical gold. Пока такого
решения и отдельного implementation/review/CI нет, critical gate остаётся FAIL;
девять cases нельзя объявлять исправленными или отложенными с waiver.

## Evidence и воспроизводимость разбора

- Existing actual artifacts: `04ff1dd-critical-baseline-cases.json`,
  `04ff1dd-critical-baseline.junit.xml`, baseline stdout/stderr; повторного
  CI audit или запуска gate не было.
- Статический source inventory:
  `04ff1dd-critical-normative-contract-source.json`, SHA256
  `9b3b37acb1395ed7fbef60ea2f0f3dc47c1abd4d0aee23b64f2e67278c0d69d6`.
  В нём 26 exact fixtures, девять retired expectations, 15 syntactic Python
  positives и hashes всех прочитанных production/tests/decision files.
- Normative source SHA256:
  `de87153f11fd00b874995b54b460010321ac21f2eb4ed7a1e8bad0328e757c87`.
- Old critical test SHA256:
  `cdbd5a423c6042edd0e0d626144c04f93302aacecce3fb17941b1818b7f2433e`.
- Critical gate SHA256:
  `d2940c8df624ce8070fdf4200531c43354e068e98ea9c1acee3a6f342effff2d`.
