# PR211: независимый review fidelity insufficient DTO

Дата: 2026-10-08. Base: `3be9c34afa49dcf4278d2910ec29ed37c305225c`.

**Вердикт: APPROVE** для узкого test-only slice:

- `tests/docs/test_model_visible_projection.py`: SHA-256
  `ccc0958f996d3ecd74a6429bfda643eb0388d5799edcccbf2205f23414608cf7`.
- Авторский `PR211_MODEL_VISIBLE_FIDELITY_REVIEW_RU.md`: SHA-256
  `ed936703f758b627cef15732ef829f0eba3fd326b72e278a5359acb280d2c2cb`.

Одобрение относится к корректности миграции и сохранению проверяемых guards.
Runtime этой версии **NOT RUN**; full acceptance и устранение других failures
из него не следуют.

## Контракт и первый фактический failure

Сверен настоящий core Python 3.12 JUnit run `37824782946`, artifact
`11571391371`, ZIP SHA-256
`5a432090f914db6ca88a2bc2eaf74ce4dd25ffd0d76a1e8fc38fa8daea9756a9`.
Все четыре исходных nodes
`test_oversized_insufficient_projection_uses_a_valid_terminal_fallback`
с параметрами **256, 300, 1500, 2000** упираются в прежний `estimate <= budget`;
actual baseline estimate равен 7650. Новый test не закрепляет это фактическое
число как expectation.

Прочитаны `V4_PRODUCT_DECISIONS_RU.md` (отдельная миграция отменённых docs output
caps с сохранением fidelity и safety), `NEXT_PARALLEL_IMPLEMENTATION_PROMPT_RU.md`
(различие representation и acquisition/security/work bounds), production
`bound_insufficient_projection`, `_refresh_estimate` и полный insufficient branch
`validate_model_visible_projection`.

Вызов получает уже сформированный public DTO: sources отсутствуют, нет query,
acquisition, source read, provider либо admission operation. Текущий producer
обновляет только `estimated_tokens`; `_refresh_estimate` имеет прежние три
итерации. Текущий validator проверяет форму и authority, но не отбрасывает этот
готовый insufficient DTO по `max_tokens`. Поэтому старые требования усечения
и удаления `missing_requirement_ids` несовместимы с утверждённым контрактом
этого вызова. Перенос этого вывода на retrieval acceptance 800, read bounds,
source caps, schema либо другие gates данным slice не разрешается.

## Независимая проверка diff

Stdlib AST и сравнение bytes против base подтвердили:

- Изменён только body одного существующего parametrized test. Signature и
  decorator прежние; четыре concrete nodes не добавлены и не удалены.
- Другие 31 test functions и остальные 38 module nodes неизменны. Prefix до
  первого body statement и suffix после функции совпадают побайтно.
- Все прежние payload values сохранены AST-exact, включая исходные action
  observations, 100 requirement IDs и семь hashes. Вложенные поля action
  проверены отдельно, а не только внешние dict keys.
- Добавлены только явные sentinel values: top-level false edit/documentation
  authority, true hard_stop/confirmation и action confirmation reason,
  confirmation true, auto_execute false.
- Из четырёх прежних assertions две проверки representation loss заменены
  fidelity successors. Отсутствие `support_envelope` и вызов validator с теми же
  `snapshot={}` и `max_tokens=budget` сохранены AST-exact.
- Новый body содержит 13 Assert nodes и восемь negative variants внутри
  существующего цикла. Это 32 authored negative iterations по четырём budget
  cases, не 32 новых nodes и не выполненные runtime checks.

Production `model_visible_projection.py` совпадает с base побайтно, SHA-256
`f78f41fb46f3ff57222b3e95837024fc36dbe82100d14fee89c56785e89a271a`.
Shared helper, imports, diagnostic inventory, thresholds, production и соседние
tests данным slice не меняются. `git diff --check` для target file чист.

## Fidelity positive и сохранённые guards

До вызова input независимо копируется через `deepcopy`. После вызова весь
payload должен равняться этой копии, дополненной лишь текущим
`estimated_tokens`. Expected diagnostics не получены из output projector:
удаление либо замена любого текста, requirement ID, hash, action field или
неожиданное добавление поля нарушит сравнение. Сам исходный `missing` содержит
14 000 ASCII characters, поэтому positive невакуозен и заведомо больше всех
четырёх прежних budget values. `measured_tokens > budget` фиксирует именно эту
границу, не вводит новый ceiling.

Отдельные assertions явно сохраняют полные missing lists/action и проверяют
bool identity: `False` не заменяется числом 0, `True` — числом 1. Сохраняются
answer/documentation/edit denial, hard_stop, confirmation и запрет auto_execute.
Пустой terminal fallback и opaque support-envelope replacement больше не
считаются успешным сохранением уже готового DTO.

Каждый negative variant начинается с отдельной копии этого же valid positive,
затем обновляет estimate и требует свой точный error label:

| Изменение | Действующий validator guard |
|---|---|
| Некорректный kind | `invalid projection kind` |
| Некорректный status | `invalid projection status` |
| answer_supported=true | `insufficient evidence has inconsistent answer_supported` |
| answer_available=true | `insufficient evidence has inconsistent answer_available` |
| support_status=ok | `insufficient evidence has inconsistent support_status` |
| edit_ready=true | `context projection must not authorize edits` |
| Непустая implementation_guidance | `insufficient evidence must not authorize edits` |
| Внутренний diagnostics object | `forbidden model-visible keys: diagnostics` |

Все labels сверены с реальными production branches. Обновление estimate после
mutation исключает использование stale estimate как единственной причины
отказа. Значения confirmation/hard_stop здесь проверяются на fidelity, а не
выдаются за полный validator всех recovery grants. Sentinels не предоставляют
разрешение на side effect; никаких действий этот test не исполняет.

Проверяемые hash strings — уже переданные DTO values. Их сохранение не объявляет
их canonical semantic proof: source/hash/span binding и реальный admission
сохраняют отдельные неизменённые проверки. Авторский report правильно обозначает
эту границу и не распространяет вывод на остальные cap tests.

Repository modules не импортировались; pytest, installer, server/client,
provider и дополнительные retrieval pilots не запускались, зависимости не
устанавливались. Нужен совместный CI на конечном опубликованном SHA с проверкой
этих четырёх nodes и отсутствия новых regressions.
