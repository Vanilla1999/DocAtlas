# Промпт: существенное сокращение тестов DocAtlas / PR #211

Ты — координатор мультиагентной работы. Используй несколько агентов для
независимых областей, затем отдельного reviewer. Задача — реализовать чистое
сокращение активных тестов минимум на40%, начиная с разбора красных, и заменить
малополезные проверки реальными интеграционными сценариями. Не ограничивайся
предложением или удалением46 уже подготовленных cases.

## Контекст и источники

Прочитай:
- `AGENTS.md`;
- `v2plan/TEST_REDUCTION_40_ANALYSIS_RU.md`;
- `v2plan/TEST_STRATEGY_INTEGRATION_FIRST_RU.md`;
- `v2plan/PR211_CHECKPOINT_RU.md` и `CURRENT_WAVE_DECISIONS_RU.md`;
- `v2plan/PR211_TESTS_AND_ACCEPTANCE_PLAN_RU.md`;
- существующие retirement manifests только для затронутых семейств.

Анализ сделан на `c518359f`; старый основной checkout может отставать.
Последний прочитанный в анализе core CI136:7669cases,6052PASS,1607FAIL,10SKIP.
Это история другого SHA, не готовый baseline текущей работы. GitHub API при
анализе вернул401. Не обещай доступ к CI; восстановление credentials выполняет
владелец, не меняй auth/permissions самостоятельно.

Если новые документы ещё только локально в `analysis/pr211-test-strategy`,
сначала сохрани и перенеси именно эти изменения в рабочую integration-ветку
без чужих файлов. Не предполагается, что они уже доступны из remote PR.

## Цель и честный подсчёт

1. Зафиксируй BASE_SHA/merge tree и unique expanded roster активных core+advanced
   проверок из одного авторизованного baseline. Live/клиентские проверки и
   standalone gates учитывай отдельно, не позволяй скрыто увеличить их работу.
2. `TARGET_REMOVAL = ceil(0.40 * N_before)`;
   `N_after <= floor(0.60 * N_before)`. В N_after входят все новые проверки.
   Для исторического core7669 ориентир3068 net removals и4601 remainder.
3. Считай unique node IDs и логические сценарии, а не сумму Python lanes,
   workflows и repeated attempts. Смена имени/маркера/selector не даёт removal credit.
4. Покажи отдельно removed, added, renamed/moved, net; время, public calls,
   mutation executions и объём artifacts. Перенос cases в цикл не сокращение.
5. Если обоснованный manifest пока не даёт40%, расширяй анализ зелёных дублей.
   Не заполняй недостающую квоту непроверенными удалениями. Отчёт ниже40% —
   незавершённая цель с точным gap, а не повод фальсифицировать результат.

## Непересматриваемые правила

- Новые проверки только integration/system/installed/client/production-like.
  Переиспользуй существующие runners и case data; не строй новый framework.
- Исходный вопрос → настоящий API/CLI/MCP → реальные компоненты/storage →
  конечная выдача → независимые обязательные факты/source/hash/span/scope/version.
- Не mock-ать проверяемые retrieval, selection, storage, validation. При
  изоляции внешней сети честно указывай, какая граница не проверена.
- Не менять frozen original questions, gold facts, quality floors и consent/
  access/authority/source guards ради сокращения или зелёного отчёта.
- Цвет теста не причина удаления. Первый failure не классифицирует весь модуль.
- Удалённый product reproduction должен оставаться в integration с тем же
  semantic verdict до исправления продукта. Product fixes — отдельный diff.
- Не требуй1:1 replacement или mutation receipt на каждый дубль. Проверяй
  различный риск на уровне семейства; используй existing regressions/receipts.
- Не добавляй skip/xfail/collection filters ради −40%; не переноси набор в
  nightly/advanced и не отключай required gates под видом удаления тестов.
- Работай с существующими разрешёнными CI. Ограничение локальных runtime,
  imports/AST/pytest/install из checkpoint сохраняется до явного изменения
  владельцем. Не обходи его и не считай статический анализ runtime PASS.
- Не трогай пользовательские индексы; не подключай новые providers/models/
  downloads. Реальные client sessions не заменяются scripted installed smoke.
- Никаких force-push, merge, release. Итог в одной PR-ветке; обычный push
  только в пределах действующего поручения владельца.

## Фаза 0 — координатор фиксирует базу и владение

Проверь git status, PR head и наличие нужных документов; сохрани чужую работу.
Получай существующие JUnit/artifacts read-only. Если доступа нет, продолжай
статическую классификацию, но не интегрируй непроверенные удаления и точно
запиши, какого artifact/run не хватает для проверки.

Создай один общий manifest, а не отдельный отчёт на каждый тест. Поля:
`family`, `base_sha`, `old_nodeids`, `baseline_status`, `behavior`,
`decision`, `contract_or_successor`, `evidence`, `removed`, `added`, `owner`.
Допустимые decision:
`DELETE_OBSOLETE`, `DELETE_DUPLICATE`, `REPLACE_INTEGRATION`,
`KEEP_PRODUCT_FAILURE`, `UNRESOLVED`.

Красные сначала, затем зелёные в тех же семействах и во всём roster.
Для каждой семьи сделай точный список файлов-владений: один файл — один writer.
Агенты предлагают изменения общих fixtures/labels/workflows координатору;
самостоятельно общие файлы не редактируют. Не запускай вложенных агентов.

## Фаза 1 — три независимых исследователя

### Агент A: отменённая семантика и избыточные входные матрицы

Исследуй question-plan, generated aliases, roles, inferred authority,
compositional frames. Начни с подготовленных QP26/role19/default3–800 case,
затем query_planning*, answer_units, project_answer_contract, patch plans.
Условия ранее подготовленных46 retirements не объявляй выполненными без их
собственного доказательства. Сохраняй исходные frozen questions, literal
identity, Unicode/span и отсутствие inferred authorization публично.

### Агент B: mock/facade/service слои и повторные state сценарии

Исследуй docs_service*, unified_docs_context*, routing и lifecycle fixtures.
Раздели FakeFacade/call-count/internal flags и настоящие rename/delete/restart/
CAS/source-isolation задачи. PermissionError на старой entrypoint не повод
стереть задачу; используй явную current transaction и реальный state outcome.
Предлагай объединение по поведению, включая зелёные cases.

### Агент C: зелёные DTO/schema/snapshot и delivery дубли

Исследуй dictionary_exit*, action_packet*, evidence/projection и schema
surfaces — только точные файлы, выданные координатором. Сопоставь с уже
существующими public/installed/adversarial сценариями. Убирай повторные
внутренние snapshots, не теряя real source/hash/span/scope/consent проверок.
Read_next, source fidelity и public retrieval failures выделяй отдельно:
они не устарели только потому, что тест красный.

**Выход каждого агента:** строки общего manifest, exact file/node scope,
существующий successor или минимальное расширение integration, подтверждённый
объём и неподтверждённые кандидаты отдельно. В этой фазе тесты не удалять.
Не назначай агентам квоты удалений: они стимулируют подгонку вместо анализа.

## Фаза 2 — координатор выбирает пакеты, агенты реализуют

Сверь пересечения и подведи количественный итог. Priorities:
1. Документированно отменённые требования и уже подготовленные retirements.
2. Дубли, уже защищённые сильным существующим integration.
3. Крупные семейства, заменяемые небольшим набором public сценариев.

Раздай непересекающиеся пакеты тем же A/B/C. Временные worktrees — от одного
BASE_SHA; отдельные обычные commits. Source fixes, oracle changes и test deletion
должны быть различимы в diff. Не восстанавливай старый production-контракт
ради старых тестов. Не уменьшай качество ответа ради упрощения проверки.

Удаляй ненужные test helpers, imports/reexports, fixtures и labels только
после проверки их реальных consumers. Исторические receipts сохраняются.
Git хранит удалённый код: новые архивные копии тестов не нужны.

## Параллельная задача координатора: управляемая трасса и CI reuse

Сначала используй существующий self-host/quality runner, same-call observer
и final projection diagnostics. Если нет настоящего OFF, минимально добавь
один host-level переключатель сбора трассы. Не вводи новый MCP argument,
который меняет продуктовый контракт, и не создавай отдельную logging framework.

Один существующий integration проверяет OFF→ON→OFF на эквивалентных snapshots:
тот же конечный business payload/source bindings/state/public-call count,
trace появляется только при ON, protocol stdout чист. Обычные ошибки не
скрываются при OFF. Для разбирательства сохраняй original request и полный
final response в контролируемом artifact; previews не выдавай за полную выдачу.
Нельзя повторно вызывать retrieval из observer. Отдельный replay имеет свой run ID.

CI/P1 reuse делай отдельным scoped commit: эквивалентный producer выполняется
один раз; required consumers проверяют SHA/tree, runtime/deps, selection,
полноту artifact и producer attempt. Без результата consumer не получает PASS.
Экономию повторных executions не прибавляй к40% физических case removals.
Если эта задача тормозит retirement, отчитай её отдельно, не блокируй готовые семьи.

## Фаза 3 — независимый reviewer

После появления diff запусти отдельного reviewer, не автора удалений.
Он проверяет точные deletion manifest/diff и представительные тела всех
затронутых семейств, frozen inputs/gold, successor coverage, live guard
paths и возможное сокрытие failures. Его approval — смысловой review,
а не замена runtime. Не требуй повторного полного аудита тысяч repo blobs.

Конкретные основания отклонить пакет:
- удаление только потому, что FAIL;
- утрата уникального пользовательского поведения;
- fake integration с mocked проверяемой цепочкой;
- expectation вычисляется тем же producer либо переписана под actual;
- количество уменьшено через skip/marker/renaming/hidden loops;
- product failure или отсутствующий report выдан за PASS;
- более дорогая новая mutation/runner матрица вместо удалённой.

## Фаза 4 — проверка и интеграция

Сначала целевой разрешённый CI для пакета. Healthy integration проходит;
исторический regression/существенный directed fault ломает ожидаемый
semantic outcome. Import/setup crash и случайный nonzero — не доказательство.
Для дублей переиспользуй текущий valid proof, не повторяй mutation на каждый node.

На итоговом SHA проверь full collection, active selectors/labels и необходимые
required/downstream результаты. Суммируй удаления по unique identity, учти
новые случаи и реальные внутренние операции. Завершённые58 и literal702→82,
произошедшие ДО BASE_SHA, не считаются новой экономией.

Интегрируй только reviewed пакеты с необходимым собственным evidence в одну
ветку PR211 обычными commits/fast-forward. Если продукт всё ещё падает,
фиксируй текущий статус; это не запрещает обоснованное удаление независимых
дублей, но запрещает заявлять merge-ready.

## Итоговый ответ владельцу

Кратко, с проверяемыми числами:
1. BASE_SHA и FINAL_SHA; N_before/N_after, removed/added/net/%.
2. Какие семейства удалены и какие integration сценарии остались.
3. Продуктовые FAIL до/после отдельно от отменённых ожиданий.
4. Реальные calls/время/mutations/CI duplication до/после либо NOT_MEASURED.
5. Логи: как включить/выключить, где artifact, результат parity.
6. Required CI/client status и точные оставшиеся blockers.

Не заканчивай после первых46 удалений. Доведи обоснованное сокращение до40%
либо покажи конкретный доказательный/продуктовый blocker и недостающий объём.
