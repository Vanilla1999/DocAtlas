# 40 вопросов на запушенном8605cbdb

## Итог

Все40 context calls завершились: **22/24 positive,8/8 documented partial,
0/8 strict-empty negative**. По прежнему составному критерию30/40 PASS.
Не измеряются сгенерированные ответы: model calls0.

Источники/границы/scope/version/authority и read-only проверки:40/40 без нарушений.
Полный native DTO budget:40/40 укладываются в12000 по независимому
max(o200k_base,ceil(UTF8/4)), максимум12000, median11963.5.
Корпус, вопросы, oracle, evaluator и продукт неизменны:462 frozen files проверены.

## Исполнение

- Продукт8605cbdbb52150fc2752dc7d1544e1e90a4052b7 сначала закоммичен/запушен.
- Installed wheel, Python -I, public in-process MCP, real isolated member SQLite;
 5 confirmed prepares,40 get_docs_context,0 resources,0 models, без mocks.
- Current default без experiment admission/selector flags. Label V0 — только
  compatibility runner label, НЕ старый91dd2b4e baseline.
- Общая серия170.659s; сумма context time167.620s; median3.167s, max7.982s.
- Trace включена; её время входит в измерение. Нет claim production latency.
- Дополнительная historical whole-source packing не ухудшила ни одного
  documented claim: native30/32 и packed30/32.
- Source counts39–43 на вопрос; фактическая выдача почти всегда заполняет бюджет.
- Saved pretty JSON:504882 tokens; packed source JSON:469570 tokens, max11808.
  Saved pretty JSON не protocol serializer и не billing/full model prompt.

| Семейство | Positive | Partial | Strict-empty negative |
| --- | --- | --- | --- |
| Black |5/5|2/2|0/1|
| Poetry |4/5|1/1|0/2|
| Textual |5/5|2/2|0/1|
| Vite |5/5|1/1|0/2|
| ESLint |3/4|2/2|0/2|

## Два positive FAIL

### V40-P03 — Poetry environment variables

Вопрос: как имена configuration settings преобразуются в environment variables?
Фиксированный witness: configuration.md102–114.

Основное правило **доставлено**: prefix POETRY_, uppercase, dots/dashes→underscore,
в exact source window102–111. Не доставлен оригинальный code example112–114:

```bash
export POETRY_VIRTUALENVS_PATH=/path/to/virtualenvs/directory
```

Упоминание этого variable в другом фрагменте не заменяет исходный witness span.
Прежний строгий критерий остаётся FAIL; его нельзя переписать ради PASS.
Это потеря полноты исходного окна/примера, а не доказанная потеря основного правила.

### V40-E01 — ESLint flat configuration filenames

Вопрос: какие filenames допустимы для flat configuration?
Фиксированный witness configuration-files.md19–30 полностью отсутствует.
В выдаче есть примеры eslint.config.js, но нет eslint.config.mjs/.cjs/.ts/.mts/.cts.
Это существенный пропуск необходимого списка, не только крайних whitespace.

### Где произошла потеря

Оба witness отсутствуют уже в native public DTO, не только во внешнем packed.
Точную раннюю границу acquisition/admission/selection/budget установить нельзя:
trace bounded и неполна. P03 core.output167 источников, final42; E01 core256,
final40. Core previews содержат только64 rows; omissions103/192.
Flow event omissions1974/1982; почти вся сохранённая trace занята recheck rows.
Отсутствие witness в таком preview не доказывает его отсутствие в core pool.

`POSITIVE_FAILURE_ANALYSIS.json` содержит independent quotes, missing coordinates,
term/source observations, counts и явный UNKNOWN первой причины.

##8 negative FAIL

B08/P07/P08/T08/V07/V08/E07/E08 вернули40–43 source rows вместо empty sources.
Это **FAIL неизменённого strict-negative контракта**. Source validity не фильтрует
семантически нерелевантные документы; false answer/edit authority не равна
успешному распознаванию недостаточности.

Непустые источники не означают, что продукт сгенерировал latency/SLA/TTL guarantee:
ответы вообще не генерировались, authority остаётся false. Поэтому здесь нельзя
объявлять ни отсутствие галлюцинаций у модели, ни8 сгенерированных галлюцинаций.

## Вывод и следующий шаг

API fixes прошли отдельный installed SDK gate, но40 MCP questions не проверяют
explicit SDK expansion и не доказывают причинный gain именно этих fixes.
Открытый V40 не новый blind holdout; paired current baseline здесь не исполнялся.

Основные открытые проблемы: отсутствие semantic abstention, существенный E01
miss и неполная trace ранней потери. Нативный first-order packing под почти
постоянный полный budget не гарантирует полноту/компактность/полезность.

Перед новым методом: один отдельный E01 scenario с полной, ограниченной нужными
границами acquisition→admission→selection→budget trace и независимыми witness
проверками. Без переписывания oracle, без повторения всей40 серии и без настройки
ранжирования на её ответах. P03 диагностировать как original example retention.
После установленной причины — отдельное исправление и только затем сравнение
одного обоснованного selection/sufficiency кандидата при равном final budget.

## Артефакты

- PROTOCOL_RU.md, INTERPRETATION_RU.md, RUN_CONFIG.json, WORKER.json, FROZEN_RUN.json.
- SUMMARY.json: все40 judgments, failures, independent quotes/claim flows и costs.
- NATIVE_BUDGET_CHECK.json, INPUTS_UNCHANGED.json.
- POSITIVE_FAILURE_ANALYSIS.json.
- run/V0: оригинальные payload/metadata/integrity/packed/trace, snapshots,
  execution ledger, summary и installed wheel-file hashes.
- assessment/CASE_RESULTS.json: unchanged independent evaluator judgments.
- summarize.py: offline aggregation,0 product calls.

Raw receipts и assessment публикуются lossless archive с per-file SHA manifest;
локальные распакованные копии сохраняются. Число повторных product calls0.
