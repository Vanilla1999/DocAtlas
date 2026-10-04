# Compact-read: код исправления, native acceptance NOT_RUN

База: `5a60ba404b9b296736880769f7e89c5ac8ccc982`, ветка
`next07-feasibility-audit`. Пользователь разрешил убрать 800/3 и попросил push.
Коммит `3026969d` недоступен через GitHub (422). Его scope-wiring, диагностические
outputs и изменения неизвестны; данная правка их не заменяет и не воспроизводит.
При объединении с локальным 3026969d сохранить его scope-проводку. Не делать reset
или force-push и не выдавать эту базу за тот же dirty baseline.

## Три отдельные ответственности

1. `_payload([])` теперь возвращает `insufficient_evidence`, пустые sources,
   context_available=False и False answer/edit flags. Ни ложного successful DTO,
   ни утверждения, что факта/документа не существует. Validator не ослаблен.
2. Audit сохраняет physical line endings: `read_bytes().decode`,
   `splitlines(keepends=True)`, точный диапазон. Новый source_coordinates также
   проверяет char→line mapping. В packer неправильные входные координаты
   отклоняются, а не чинятся поиском похожей цитаты в другом месте.
3. Новый явно включаемый read-output режим задаёт max_tokens/max_sources/
   max_snippet_chars=None. Это отсутствие продуктового предела, не большое число.
   Packing и настоящий handler validator читают одну caller-owned политику.
   `_docs_source` получает явный optional snippet-size limit. Source/hash/schema/
   proof/edit проверки не фильтруются. Политика не считывается из source/payload.

## Использование

Обычный запуск без флага сохраняет старый bounded comparator. Новый режим:

```sh
DOCATLAS_OFFLINE=1 .venv/bin/python -m pytest -q \
  v2plan/test_next07_compact_delivery.py \
  v2plan/test_next07_grounded_public_wiring.py

# OUT/native должен ещё не существовать; OUT можно создать через mktemp.
DOCATLAS_OFFLINE=1 .venv/bin/python -m v2plan.next07_grounded_final_run \
  --compact-read --out "$OUT/native"
```

Для N/C corpus-runner новая C revision включается явно:

```python
from docmancer.docs.domain.read_delivery_limits import COMPACT_READ_LIMITS
with installed(service, trace, delivery_limits=COMPACT_READ_LIMITS):
    capture = capture_public_call(service, request)

# После выхода из C scope аудитор тоже получает policy от trusted caller,
# а не угадывает её по содержимому packet. N — без этого параметра.
errors = audit_payload(capture['public_payload'], trace['final_snapshot'], root,
                       delivery_limits=COMPACT_READ_LIMITS)
```

Runner сохраняет фактическую стоимость без требования <=800; проверка source
count не ограничена 3. Фактические факты/условия/flags проверяются как прежде.
Он дополнительно вызывает source audit на финальном handler snapshot, не на
копии до capability binding. Итог успешного целевого запуска имеет новое имя
`VALIDATED_LOCAL_COMPACT_TARGET`, не переписывает старый I.4 или N10.

## Краткость и пределы

Выдача состоит из целых разрешённых original windows; exact duplicate/contained
окна не повторяются. Нет пересказа, semantic compression, новых relevance veto
или guessed answers. Это не доказательство минимально возможного context.

Сохраняются прежний ограниченный search inventory, caps чтения/разбиения и
owner/dependency guards. В частности, структурный hard max 5000 и ограничение
candidate pool 20 не сняты этой правкой. Нельзя обещать, что длинный owner теперь
обязательно доставится: снят лимит выдачи, не построен новый retrieval/assembly.
N10 не исправлен. Требование whole owner не ослаблено. Новая выдача может быть
длиннее и включать больше irrelevant material; это отдельная измеряемая цена.
Production/defaults и proof/edit budgets не переключены. Public schema unchanged.

## Реально выполненные проверки

86 PASS в dependency-isolated loader: 60 новых contract checks и 26 прежних
wiring checks. На старых empty/audit definitions контроль дал 7 FAIL / 1 PASS.
Python/AST проверки выполнены. Fetched full model_visible_projection.py до
правки совпал с upstream blob `457fb02ed358d01a5f3361eb18a9554b3133aae3`.
Новая версия меняет в нём только size-условия validator и параметр renderer;
остальные определения совпадают по AST. Research candidate целиком неизменён:
SHA-256 `5ac8e2600a12d216070087a50c9ddc64c8efaaff2f399d70e2b345db0bf71ff7`.

Ограничения локального запуска: нет полного checkout/dependencies из-за DNS.
Выполнены настоящие определения validator, payload и packer с изолированными
imports. Read decision в packing tests — явный spy, не проверка source eligibility.
Стоимость — byte lower bound вместо отсутствующего pinned codec; native
числа tokens не измерялись. Nontrivial coverage/proof paths не проверялись.
Стандартный test-module в checkout использует настоящие project imports.
Результаты/hashes — result.json; raw logs/JUnit и точный local loader включены
в приложенный в чате архив next07-compact-fix.zip. В этом каталоге также сохранён
raw зелёный log. Старые artifact files не перезаписываются.

## NOT_RUN / честный итог

Новый native MCP P1/P2/P3, 80 N/C, historical 49, partial retention, N10 rerun,
full suite и release gates — NOT_RUN. Нельзя объявлять пользовательские 53/60
line-errors исправленными поголовно: новые packets 3026969d здесь не прочитаны.
Код устраняет воспроизведённую ошибку newline audit, не доказывает исход каждой
из этих цитат. Empty formatting fix не равен recovery потерянных фактов.

Rollout NOT_AUTHORIZED. Исторический candidate verdict REJECTED_N10_UNCHANGED.
Следующий проверяемый результат — actual compact packet и переаудит сохранённых
outputs, затем качество/retention; не новый threshold/parser под failed case.
