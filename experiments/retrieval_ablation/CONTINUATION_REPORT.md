# Продолжение T00–T04: project packet, изоляция и повтор регрессий

Дата: 1 октября 2026, Europe/Warsaw. Это продолжение диагностического этапа,
а не завершённая A–E ablation и не разрешение на merge/activation.

## Ревизии и публикация

Удалённая ветка `experiment/retrieval-ablation-t00-t04` при повторной проверке
оставалась на `e2ea07f1d2d3ea6ddf2718673447ee7798287671`. В этой сессии доступны
GitHub reads, но нет write/push-инструментов или настроенного CLI-доступа.
Удалённые коммиты, PR и main не изменены.

Полная история до прежнего measured code восстановлена из сохранённого Git
bundle. Два последующих документационных коммита восстановлены как локальный
snapshot `56d2b6e`: его tree **точно совпадает** с tree удалённого e2ea07f1 —
`3a8b57f5ce1c7bad332acd1995bbb3bd3c2ac8ae`. Это не подмена Git-истории удалённой
ветки. Поставляемый format-patch содержит только изменения ПОСЛЕ этого snapshot;
вспомогательный restoration commit в него не входит.

Локальные изменения:

- `bd12496c4ccb846d8bc0511150588c2f1859a577`: project-only PacketPort, OS worker,
  label-free helpers, regression runner, тесты и конфигурация workflow.
- `9ecc38a31cbbb9f0dc5e80358deaf8aa872e296b`: ограниченный захват вывода при
  отделившемся дочернем процессе; дополнительный защитный тест.

- `926b8dbd41d7e18426a8c4a82a75ed3980cbe3e5`: staging берёт только tracked runtime-файлы; неотслеживаемый sidecar не может стать незамороженным входом.

**Финально измеренный код — 926b8db.** Последующий отчётный commit не меняет код.
В приложенном архиве — patch, изменённые файлы и фактические логи/JSON/JUnit.
Новый workflow в GitHub не запускался; старый CI не считается новым прогоном.

## Реализация

### T02/T04: ограниченный настоящий A packet

`ProjectPacketPort` работает с явным unversioned project scope и текущим
каноническим Markdown snapshot. CLI сохраняет реальный `project_file` source
class, а не подменяет его синтетическим значением из unit fixture. Проверки
проекта, источника, lifecycle/risk, снимка и диапазонов остаются до exposure.

Настоящий `SourceReferenceContext` восстанавливает source/owner witnesses.
`prepare_reference_probe` и `qualify_evidence` выполняются на реальных объектах;
заголовок дополнительно сверяется с исходным parsed owner. Подложный заголовок
в metadata не может переименовать владельца. Exact/reference rejection не
отключаются вместе с лексической релевантностью.

Исключение узкое: обходится лишь `insufficient_visible_match`, когда настоящий
trace подтверждает отсутствие missing exact terms. Остальные причины отказа
сохраняются. Это **lexical-ratio-only ablation**, не снятие всех soft gates.
Trace не переписывается в `qualified=True`.

Отбор идёт в сохранённом порядке native SQL lanes. Реальные renderer, snapshot
builder и `docs_context_budget_tokens` проверяют весь DTO: максимум 800 токенов,
3 source entries, 2 sections/document. Берутся целые уже индексированные children;
непомещающиеся пропускаются, а не режутся. Финальные source/reference и DTO
проверки повторяются. Контекст не получает coverage, answer/edit authority.

Library/versioned/incomplete scopes всё ещё дают `BLOCKED_SAFE_PACKET_ADAPTER`.
Пустой допустимый результат — настоящий insufficient-evidence DTO, а не успех
семантической оценки. Combined semantic sufficiency не измерена. A не становится
новым публичным MCP runtime; исправление representation/атомарности — будущий B.

### T03: реальная граница процесса

CLI staging содержит только source allowlist, production runtime и необходимые
label-free helpers. Linux user/mount/network/PID namespaces дают отдельный root,
read-only `/app` и `/public`, writable `/output` и private scratch. Нет host
`/proc`, home, `.git`, наследуемых секретных переменных/дескрипторов или доступа
к host loopback. После chroot снимаются capabilities и включается no-new-privs.

Тесты реально пытаются читать private labels по абсолютному пути, менять public
source, remount, подключаться к host loopback и получать host environment.
Без namespace capability — `BLOCKED_ENV`, без небезопасного fallback.

Это sandbox для доверенного экспериментального кода, не универсальная защита
от произвольного враждебного workload. Private review должен находиться вне
установленных Python/system runtime prefixes. ОС-изоляция сама по себе не
создаёт независимый holdout.

### Устранена скрытая загрузка gold

Первый изолированный запуск выявил, что прежний fixture helper импортировал
self-host gate, который при импорте читал `cases.json`. Файлы эталонов не стали
добавлять в mount. Вместо этого service fixture импортирует те же production
классы напрямую; existing observer и canonical audit отделены от оценки.

`audit.py` содержит прежний `audit_payload` с неизменённым AST. `public_call.py`
содержит прежнее same-call наблюдение с явным dispatch parameter. Старый script
сохраняет совместимую обёртку и свою точку monkeypatch. Ни semantic reviewer,
ни evaluator runner, ни labels в staged worker не попадают. Public handler и
его product pipeline не заменялись самописным поиском.

### Парная диагностика

`regressions` запускает неизменённые тесты и обычный conftest в свежих процессах.
Base/head используют один и тот же owned checkout path и pytest basetemp; порядок
чередуется. Target-only и full-collection условия сохраняются раздельно.
Команды, exit codes, testcase IDs и сообщения не нормализуются до «зелёного».

Timeout завершает собственную process group. Захват stdout дополнительно
ограничен, если потомок отделился от группы и удерживает pipe. Это не обещание
убить произвольные detached процессы; runner — доверенная тестовая диагностика,
не sandbox. Guard создаёт и затем явно убирает только свой detached child.

## Выполненные проверки

Фактическая локальная среда: Python 3.13.5 / SQLite 3.46.1, одинаковый установленный
inventory внутри каждой пары, `DOCATLAS_OFFLINE=1`, `DOCATLAS_AUTO_VECTORS=0`,
`PYTHONHASHSEED=0`. Inventory сохранён в freeze и paired summary.

**Это не полностью установленный CI lock environment:** `uv sync --frozen`
заблокирован недоступной загрузкой uncached dependency. `uv.lock` не менялся,
но один его hash не доказывает совпадение установленной среды с прежним CI.

| Проверка | Фактический результат | Ревизия/граница |
|---|---|---|
| Guards + native SQLite | **100 passed** | исходники зафиксированы в 926b8db; `release-guards.xml` |
| Из них новые continuation tests | **26 passed** | Входят в 100, не добавочные независимые случаи |
| Два старых проблемных testcase IDs | **2 PASS в каждой из 4 ячеек** | base55637 / headbd12496, по два повтора, одинаковые пути |
| Смежный observer/gate/protocol набор | **base 142 PASS / 1 FAIL; head 142 PASS / 1 FAIL** | Те же 143 IDs; нет различий статуса/сообщения; headbd12496 |
| Final isolated P | **EXECUTED**, audit `[]`, **318 DTO tokens** | 926b8db, `release-P/result.json` |
| Final isolated A | **EXECUTED / VALIDATED_PROJECT_PACKET**, audit `[]`, **289 DTO tokens** | 926b8db, `release-A/result.json` |
| Full offline attempt | **BLOCKED_ENV, exit 4; 6 collection errors, 3 collection skips** | 9ecc38a; `verified-offline-attempt/` |
| compileall / diff whitespace | PASS | Фактические команды выполнены |

Поправки после bd12496 меняют timeout accounting, tracked-only staging и их guards;
парные 143 и 2-ID результаты выше не переименованы в новые прогоны на 926b8db.
100-test набор проверил окончательные исходники перед commit; оба финальных CLI
запуска выполнены из чистого checkout 926b8db. Попытка полного offline gate
относится именно к 9ecc38a, до последнего ужесточения staging.

Единственный FAIL смежной пары —
`test_v2_inventory_lock_witnesses_and_report_only_lanes`: active witness document
revision mismatch. Он воспроизведён и на base, и на head с одинаковым сообщением;
это также FAIL прежнего сохранённого baseline CI. Исторические lock/документы
ради его устранения не изменялись.

Шесть collection errors полного offline attempt связаны с отсутствующим `w3lib`.
Никакие assertion skips/xfail или обход diagnostic inventory не добавлялись.
Полный offline suite не был выполнен; зелёного полного gate нет.

Прежние два head-only FAIL не воспроизвелись в target-only повторах. Это **не
установленная причина** старого расхождения и не доказанная flaky-классификация:
не проверено влияние полного порядка исполнения. Они остаются открытыми для
полностью установленной locked base/head проверки, без waiver.

P/A — повтор одной уже просмотренной синтетической English Markdown fixture.
Один original-only panel, 2 planned / 2 executed, 0 semantic evaluations,
0 answer generations, 0 независимых новых quality cases. P/A имели 10/2 SQL
searches и 10/2 raw hits. Эти числа и 318/289 токена — plumbing measurements,
не доказательство качества, скорости или равнобюджетного выигрыша A.

## Саморевью и исправления

- Поведенческий тест выявил подмену heading metadata; проверка actual parsed
  owner закрыла её. RED/GREEN сохранены.
- Проверка staging выявила доступность кода semantic judge. Audit вынесен отдельно,
  staged allowlist сужен; тесты недоступности reviewer и настоящих P/A прошли.
- Первая экстракция observer потеряла script-level dispatch seam: смежный набор
  дал 19 FAIL, включая один старый. Обёртка восстановила совместимость; все
  18 добавленных падений исчезли, подтверждено парой 142/1 против 142/1.
- Проверка обнаружила копирование untracked sidecar из дерева runtime, которого
  нет в frozen Git inventory. Tracked-only staging исключил этот вход; RED/GREEN
  сохранены. Новые source/runtime файлы должны быть добавлены в Git index до freeze.
- Отделившийся child удерживал stdout после group kill: реальный тест превысил
  допустимую длительность. Bounded capture исправлен и повторен GREEN.
- Ошибки fixture/импорта и обращение к отсутствующему gold не выдаются за
  поведенческий TDD RED поиска; они сохранены как отдельные development blockers.

Некоторые ранние попытки full-collection были прерваны внешним timeout, до
полного summary. Их raw файлы сохранены отдельно, но не включены в завершённые
парные знаменатели. Основные результаты — только явно названные каталоги выше.
Саморевью выполнено автором реализации; независимого maintainer approval нет.

## Решение и следующий этап

HARD_SOURCE / CANONICAL_INTEGRITY / AUTHORIZATION — **KEEP**. Изолированный
измерительный adapter — **OPTIONAL**, пока только узкий project scope.
Representation B, D_L, E_G/E_GR, dense, answerer — **NOT_EVALUATED**.
Качество/неухудшение остаются **INCONCLUSIVE**. Продуктовые эвристики не удаляются.

T00–T04 продвинуты, но весь этап не объявлен завершённым: окружение полного gate,
uncapped first-loss observations и библиотечно-версионные packet cells остаются
ограничениями. Следующая граница — законченный locked paired gate и его
причинная диагностика, затем T05/T06 на заранее зафиксированном project scope.
T05–T12 в этом продолжении не запускались. Merge/activation отсутствуют.
