# Причина двух потерь установлена: финальное бюджетирование

Выполнен только диагностический шаг1. Продукт не исправлялся, новые модели и
методы отбора не добавлялись, остальные38 вопросов не запускались.

## Доказанный путь исходных фактов

| Граница | P03 | E01 |
| --- | --- | --- |
| SQL search | Полный witness найден | Полный witness найден |
| Acquisition после resource limits | Сохранён | Сохранён |
| Admission / native selection | Допущен, сохранён | Допущен, сохранён |
| Core projection | Сохранён | Сохранён |
| После source continuation и source recheck | Сохранён | Сохранён |
| Terminal public DTO budget | **Потерян** | **Потерян** |
| Public DTO / external packed | Исходный критерий FAIL | Исходный критерий FAIL |

Это не вывод из логового флага: сохранены все source rows на каждой границе;
тексты/координаты независимо сопоставлены с pinned исходными документами.
Тот же неизменённый `evaluate.py` подтвердил полный witness перед terminal budget
и отсутствие полного witness после него. Public scope/version/authority/identity,
hash/span проверки и read-only прошли для обоих запросов.

## P03 — Poetry

Обязательный пример находится в окне chars3247–3446, rank74 среди167 кандидатов.
Окно содержит первоначальный пример и следующий пример secret setting; никакого
нового текста не создавалось. На момент budget trial выбраны42 других окна.
Стоимость trial **12130 >12000**. Окно внесено в полный список исключённых.
Итог42 sources, terminal cost11882; пример потерян, основное правило доставлено.
Before terminal cost47901; omitted125 источников.

## E01 — ESLint

Фиксированный witness chars584–1141 пересекает два исходных окна:

- chars584–993, rank137/256: полный список шести configuration filenames.
- chars993–1324, rank141/256: placement/export rule и code example.

Оба окна найдены, допущены и успешно прошли source recheck. Trial после39 уже
выбранных окон: **12139** и **12133** соответственно, оба >12000.
Итог39 sources, terminal cost11829; оба окна исключены.
Before terminal cost73138; omitted217 источников.

## Причина в реализации

`docmancer/core/_sqlite_store_part03.py:517–560`: lexical OR search возвращает
BM25 order с deterministic source/chunk tie-break; acquisition сохраняет этот
порядок. Этот rank не является доказательством достаточности/полезности окна.

`docmancer/docs/application/experimental_candidate_selection.py:114–138`:
source-valid native selection удаляет недопущенные/точные duplicates, но оставляет
все уникальные допущенные окна в исходном порядке. На observed live read обе
группы прошли; duplicate copies из повторных retrieval queries не создают новые
доказательства и удаляются.

`docmancer/docs/application/experimental_context_finalization.py:565–599`:
terminal budgeting последовательно добавляет целые rows. При `cost > cap`
проходит `continue`; уже выбранные ранние строки не заменяются более поздними.
Для этого native-rank пути `_native_alternatives` не используется. В результате
нужные поздние rows гарантированно теряют место после насыщения бюджета.

Следовательно, **первая доказанная граница потери — terminal budget**; причина —
greedy first-fit по исходному retrieval order без пересмотра набора.
Не acquisition cap, не source validator, не внешний historical pack и не новая
SDK delivery-budget ошибка. Бюджет соблюдён; полезность выбора им не гарантирована.

## Границы доказательства

-2 public context calls,2 public confirmed preparations, реальные компоненты
  установленного8605cbdb wheel, Python -I;0 моделей,0 runtime retries.
- Полный generic profiler observer, без gold-dependent фильтра и без подмены
  функций продукта.847/1292 events,0 observer errors,0 omitted events.
-463 frozen inputs не изменились. Последующий offline assessment не вызывает продукт.
- Отдельный docs MCP lookup перед edit вернул insufficient_evidence/target missing;
  использованы исходники репозитория. Он не относится к этим2 corpus calls.
-Это installed public in-process MCP, не stdio/реальный клиент/production smoke.
- Время с profiler не performance benchmark.
- Новые isolated roots/generations отличаются от V40. Нормализованные конечные
  rows не полностью совпадают: P03 одна замена при42 sources; E01 минус одна row
  (39 против40). Новый root длиннее на3 символа; полная DTO содержит меняющиеся
  identity/continuation данные, учитываемые budget codec. Причина каждого такого
  отличия отдельно не изолировалась. Поэтому **trace on/off equivalence не доказана**;
  обе исходные witness-потери воспроизведены и их budget branches наблюдены напрямую.
- Исходный строгий oracle остаётся FAIL для обоих. Качество ответа не измерялось.

## Следующий шаг

Теперь можно перейти к шагу2, но это не повод повысить budget, подставить gold
или вручную поднять E01/P03. Нужен общий механизм выбора набора **до** terminal
first-fit: обоснованное сравнение одного метода при том же полном DTO cap,
без специальных правил для этих вопросов/библиотек. Source validation/read-only
сохраняются; целые исходные окна и ограничения бюджета остаются обязательными.
Совместная доставка связанных исходных окон важна для P03 и E01, но одна лишь
adjacent expansion не устраняет установленную причину: окна уже приобретены.

Перед реализацией зафиксировать общий принцип selection и критерии, проверить
точечно эти два неизменённых сценария, затем один раз40 вопросов. Отдельная
abstention/sufficiency оценка из шага3 по-прежнему нужна: замена упаковки сама по
себе не решает8 negative cases.

## Воспроизведение и артефакты

`PROTOCOL_RU.md`, `FROZEN_RUN.json`, `WORKER.json`: pre-call pinning и ceiling.
`DIAGNOSIS.json`: independent original-gold stage judgments, verified witness
coordinates/source hashes, executed trial costs, полные omissions, read-only,
сравнение с V40 и явные ограничения.

```sh
timeout 600 /tmp/opencode/docatlas-sdk-delivery-installed-20261013/bin/python -I eval/heuristic_removal/trace_two_losses.py --manifest reports/docatlas-grounded-20261013/two-loss-boundaries/FROZEN_RUN.json --worker reports/docatlas-grounded-20261013/two-loss-boundaries/WORKER.json --output reports/docatlas-grounded-20261013/two-loss-boundaries/run/V0 --work /tmp/opencode/docatlas-two-loss-boundaries-20261013
/tmp/opencode/docatlas-sdk-delivery-installed-20261013/bin/python -I reports/docatlas-grounded-20261013/two-loss-boundaries/assess_boundaries.py
```

Product command выполнена один раз; существующие output/work повторно не запускать.
Offline assessor первоначально ошибся при сравнении relative public paths как
absolute; исправлен только offline нормализатор, без product повторов и без
изменения oracle. Raw `run/` сохранён локально и lossless в `receipts.tar.xz`;
`RECEIPTS_ARCHIVE.json` содержит per-file SHA-256 и проверку архива.
Commit/push этих новых изменений не выполнялись.
