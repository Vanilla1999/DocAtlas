# DocAtlas: следующая параллельная волна реализации

Выполни четыре направления ниже: реализация → независимый review → интеграция →
совместная проверка. Разрешаю делегирование, изолированные worktrees, локальные
commits и интеграцию одобренных изменений. Не выполняй push, merge или release.
Не останавливайся на плане, если работа выполнима в согласованных границах.

## Цель и контракт

DocAtlas должен возвращать coding agent полезные точные выдержки из подключённых
актуальных `.md` через настоящий MCP: paraphrase, несколько разделов, полезный
partial context и длинные необходимые данные.

**Не терять нужное, не отдавать лишнее, не обрезать ради числа.**

- Совместимость с предыдущей версией продукта и миграция старого API не требуются.
  Поддерживай один текущий контракт. Это не отменяет совместимость с актуальными
  поддерживаемыми MCP clients и действующие security-свойства старых tests.
- Не возвращай словари, скрытые aliases/переводы, inferred proof/edit authority,
  не подменяй вопрос ключевыми словами и не подстраивай scoring/thresholds под cases.
- Сохраняй source identity/hash/span/version/freshness, consent, access и read guards.
  Документация — данные, а не инструкции для инструментов или разрешение на edit.
- Representation/output caps можно снимать. Acquisition/search/work/read bounds,
  schema/catalog byte ceilings, gold, thresholds и CI gates этим не отменены.
- Автоматическая omission diagnostics остаётся: дополнительный probe принят
  владельцем. Не называй это acquisition invariance и не добавляй witness в ответ.

## База и короткий onboarding

Ожидаемая база: `edf1ced699aea1f8ae28a514bc12962de6aa5d18`.
Worktree: `/tmp/opencode/docatlas-premerge-s1yitbwl/worktree-integration`.
Артефакты предыдущей волны: `/tmp/opencode/docatlas-premerge-s1yitbwl/` (далее ART).
Репозиторий: `/home/viadmin/StudioProjects/hermes/docmancer`.

Проверь HEAD/status и применимые AGENTS.md, включая
`/home/viadmin/StudioProjects/hermes/AGENTS.md`. Не перезаписывай пользовательские
изменения и не переключай пользовательский checkout. Если база отличается,
сначала установи причину; не делай reset. Если артефакты отсутствуют — сообщи точно какие.

Координатор читает только:
- `v2plan/V4_PRODUCT_DECISIONS_RU.md` из основного checkout;
- ART/`CP-RESULT_RU.md`, `INTEGRATION.md`, `ROUND_CLOSURE_RU.md`.

Исходный совместный checkpoint: 365 nodes, 360 PASS / 5 FAIL, без ERROR/SKIP.
Это узкая проверка, не полный CI. Исторические разрешения относятся к своим slices;
старые integration holds B/C уже закрыты. Не повторяй весь исторический аудит.

## Параллельная работа и экономия контекста

Используй координатора и максимум четыре одновременно работающих агента A–D.
Агенты не создают вложенных агентов. Каждый получает только общий контракт,
свою задачу, выделенные пути и ссылки на нужные evidence; не копию всей беседы.

До правок создай короткий ownership ledger: файл/функция → единственный writer.
Разные worktrees не устраняют смысловые конфликты. Общий файл правит один владелец,
остальные передают ему точный change request. Каждый агент пишет свои новые tests
и разрешённые registration shards; общий manifest имеет одного владельца.

Используй существующие инструменты и окружение. Читай код по символам/путям,
логи сохраняй в файлы, в чат возвращай counts, причины и ссылки. Документацию
зависимостей запрашивай только для конкретного API-вопроса, а не заранее для всех.
Не запускай повторный аудит/тест без изменившегося input или нерешённого вопроса.
Экономь дублирование работы, а не необходимые tests или полноту выдачи продукта.

## A — основной пользовательский сценарий

Вход: ART/`A-report.md`, `R-A-proposal.md`, исходные fixtures/queries из `A-run.py`.
Проверяй актуальный код: отчёты A относятся к более ранней базе.

1. На неизменных RU/EN original-only cases установи первую границу потери:
   acquisition → qualification → retention → projection → MCP delivery.
   Переиспользуй прежнее evidence; повторяй только недостающую проверку текущей базы.
2. Исправь подтверждённые дефекты существующего retrieval/retention пути минимально.
   Явный lookup — отдельный сценарий, не замена original-only paraphrase.
3. Сохрани несколько необходимых разделов и полезные известные данные при partial;
   gaps остаются честными, полнота/answer/edit authority не появляются из backend score.
4. Проверь настоящий публичный MCP transport на fixture-owned корпусе, включая
   исходные факты, длинный хвост, unrelated/absent вопрос и источник после изменения.

Не подключай автоматически прежний `need_context` fallback: proposal был отклонён,
поскольку подключение меняет admission. Не обходи qualification incoming flags.
Если нужен новый критерий admission, изменение diversity/acquisition policy или
подготовка отсутствующего backend/model, подай один точный запрос владельцу:
текущая граница → минимальное изменение → затронутые guards → positive/negative
controls → требуемое разрешение. Не повторяй заблокированный эксперимент.
Наличие FastEmbed в коде не доказывает готовность cold member-MCP и RU/EN качества.

## B — оставшиеся output caps

Вход: ART/`C02facade-final.md`, `C02b2-final.md`, `O02-O03-APPROVAL.md`.
Проследи реальные callers, а не только объявления констант:
- `joint_context_selection`: packet alternatives и `_finish`;
- `query_block_context`, `query_block_recovery`;
- insufficient/recovery/context-tool producers;
- project packing в `_project_docs_service_part03.py`;
- `DOCS_CONTEXT_MAX_TOKENS=800`, `MAX_DOCS_SOURCES=3` и зависимые callers.

Убери оставшиеся потери уже acquired/admitted необходимых данных ради размера.
После миграции callers удали временные aliases; не замени их большим magic number.
Для каждого лимита зафиксируй: output cap или acquisition/security/work bound.
Сохрани ограниченность optional search/Cartesian work: исчерпание оптимизации
не должно уничтожать уже принятое evidence. Не расширяй acquisition под видом packing.

Проверь длинные list/table/code units, хвостовые условия, необходимые источники
сверх прежних трёх, missing/recovery data, точные quotes и snapshot bindings.
Отдельно проверь direct-question путь без explicit lookup, который мог обходить
joint/query-block ветку. Продолжения сохраняют issuer/TTL/range/replay/read guards.

`_project_docs_service_part03.py` пересекается с A: назначь одного writer до правок.
Schema-изменения передавай D, старые cap-test migrations — C.

## C — пять известных test conflicts

Вход: ART/`CP-outcomes.json` и соответствующие test bodies.

1. Мигрируй `test_patch_config_has_no_budget_or_count_sentinel` и три параметра
   `test_docs_profiles_keep_original_representation_policy` в
   `tests/test_action_packet_v4_selection.py`.
   Замени только отменённые docs cap expectations на fidelity controls;
   сохрани действующие patch config, admission, utility и остальные свойства.
   Проверки должны ловить реальную потерю данных, а не только равенство `None`.
2. Разбери `test_old_selected_quotes_are_rechecked_for_current_technical_guards[change2]`
   в `tests/test_dictionary_exit_projection.py`: cached `risk_flags=["unsafe"]`.
   Проследи происхождение поля и действующий контракт. Различай недоверенный
   descriptive metadata и авторитетный технический запрет. Не возвращай прежнюю
   semantic inference и не меняй expectation только потому, что оно красное.
   Если контракт определяет поведение — внеси минимальный fix/successor и negatives;
   если нет — предъяви точный выбор владельцу до изменения этого свойства.

Не удаляй смешанные tests целиком. Каждый изменённый guard-negative должен
стартовать с реально допустимого непустого positive и достигать нужного guard.
Сохрани параметрический roster и normal conftest. Никаких skip/xfail, обхода
inventory, скрытых исключений или переименования labels ради PASS.
Другие historical failures не считаются автоматически legacy или разрешёнными к удалению.

## D — текущая schema и clients

Вход: ART/`E-decision.md`, затем только нужные schema/validator/registration файлы.

1. Измерь текущие advertised tool catalog/input/output schemas и внутренние schemas
   раздельно. Зафиксируй UTF-8 serialization и SHA. Исторические 21 435/12 892 bytes
   не являются измерениями этой базы. Bytes и фактические model tokens не смешивай.
2. Упрости ненужную legacy-совместимость только где она реально присутствует.
   Сохрани required fields, discriminators, unknown-field/nullable поведение и
   действующую validation. Не заменяй структуру generic object или server-only
   validation, не убирай outputSchema и не строй registry/protocol ради числа.
3. Согласуй schema с B, включая ранее разрешённое снятие output-size отказов и
   `missing/module_candidates maxItems`. Не путай это с byte ceilings.
4. Действующие ceilings catalog ≤6144 и output <1000 bytes не отменены.
   Если после простого упрощения они недостижимы, предложи конкретные новые числа,
   измерения и точные test deltas одним запросом владельцу. До одобрения не меняй
   потолки/gates. Не трать итерации на сложные `$ref`-трюки ради старого числа.
5. Установи доступные версии заявленных clients: Claude Code, Codex, OpenCode.
   На доступных разрешённых clients проверь реальную видимость полного long/partial
   payload. Различай structured lane и text fallback без дублирования всего payload.
   SDK stdio test подтверждает transport, но не сертифицирует эти приложения.

Не требуй старые версии продукта. Недоступный client/version фиксируй как NOT RUN
с точным prerequisite; не подменяй его mock PASS. Schema не аутентифицирует источники.

## Проверки и инфраструктура

Адаптируй существующий ART/`CP-run.py`, а не создавай очередной общий test framework.
Сохрани normal conftest, fixture-owned storage, проверку import origins и отсутствие
provider/download/user-index effects. Его blanket descendant denial подходит
компонентам, но сам по себе не позволяет настоящий stdio: для MCP согласуй точный
server subprocess, argv/cwd/env, fixture paths и ограничения его внешних эффектов.
Не называй in-process service test настоящим transport.

Downloads, provider calls, модель/зависимости, user indexes и изменение permissions
требуют отдельного разрешения. Не обходи отсутствие окружения. Другие независимые
потоки продолжают работу, пока один ждёт конкретного решения.

Каждый агент сдаёт локальный commit и краткий отчёт: причина → изменённые пути →
контрольные свойства → команды/SHA/counts → failures/blockers → ссылка на логи.
Никаких ежедневных пересказов всех предыдущих отчётов.

## Review, интеграция и завершение

После реализации используй одного независимого reviewer для завершённых deltas,
не более четырёх активных агентов суммарно. Review исходных guards, test successors,
ownership и authority; не повторный аудит репозитория. Исправляй выявленные дефекты
в рамках этой волны, затем проверяй затронутое. Не открывай новые направления.

Координатор интегрирует только одобренные commits в отдельный worktree. При конфликте
не выбирай ours/theirs автоматически: согласуй смысл с writer и проверь результат.
На одном итоговом SHA выполни объединённый deduplicated набор:
- прежние 365 nodes с явным mapping одобренных successors;
- новые retrieval/cap/schema regressions и неизменные затронутые guard controls;
- фиксированные public RU/EN original-only, multi-section, partial, long и negatives;
- transport/client checks с честной границей evidence.

Сверь collected/executed concrete nodes, exit codes и import origins. Запускай
совместный набор после готовности зависимостей, повторяй только при изменениях/сбое.
Не суммируй перекрывающиеся runs как отдельные успешные cases.

Финал: SHA и commits; таблица четырёх направлений PASS/FAIL/BLOCKED/NOT RUN;
новые и оставшиеся failures; принятые решения; точные blockers до merge.
Успех четырёх направлений не равен release approval: downstream gates, полный CI,
installed-wheel/platform acceptance и historical unknowns остаются видимыми
по ART/`F-blockers.md` с проверкой актуальности. Не запускай их автоматически,
не объявляй main-ready без требуемого evidence. После отчёта остановись.
