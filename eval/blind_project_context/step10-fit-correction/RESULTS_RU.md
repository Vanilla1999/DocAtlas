# Этап 2: fit-whole-pair correction и EXIT feasibility

## Изменение production

Новая opt-in recipe `complete-fit-first-maxp-v4`, без deployment policy.
`WINDOW_RECIPE` V1 и `GATED_WINDOW_RECIPE` V2 не переименованы. V3 schema2
по-прежнему требует V2 scorer и historical structural v1. Default остаётся V1
внутри отдельно opt-in minimal-context; общий experimental default выключен.

V4 перед оконным разбиением проверяет всю пару question+ancestor+body+special
tokens. Помещающаяся пара оценивается один раз на lane. Непомещающиеся входы
используют историческое полное token-overlap разбиение, включая длинный вопрос.
В V4 observer добавлены фактические half-open token intervals query/ancestor/body
для каждой реально обработанной пары, с lane и whole_pair. Это token offsets,
не source character spans. Исходный текст доставки не декодируется из tokens.

Own-body gate и fit-first нельзя одновременно включить: не объявляем новую
комбинацию старой recipe. load_policy проверяет текущую recipe, fingerprint уже
включает её; schema1 может описать новую V4 только новым явно подготовленным
artifact, старые V1/V2 policies ей не соответствуют. Schema2 V3 остаётся V2.
Новый threshold не создавался и старый не переносился.

Предпочтение sentence/paragraph boundaries ОТЛОЖЕНО: это изменит входы длинных
пар и потребует отдельного обоснования. Полное выполнение §5.3 не заявляется.
Structural policy v1 не менялась. Эффект correction на false positives не измерен.

Изменённые interfaces: `complete_context_scoring.py`, `minimal_context_selection.py`,
`probe_minimal_delivery.py`, `run_gap_agent_study.py` (recipe allowlist).
Расширен существующий public diagnostic `probe_minimal_structure.py` отдельным
режимом `--fit-correction`; исходный structural-stage режим сохранён.

## Публичная targeted проверка

Команда успешной попытки из checkout:

```sh
PYTHONPATH=. /tmp/opencode/step10-v3-py313/bin/python -m eval.blind_project_context.probe_minimal_structure --fit-correction --model-dir /tmp/opencode/step10-mini-assets --work-dir /tmp/opencode/step10-fit-v4-public-02 --output /tmp/opencode/step10-fit-v4-public-02/receipt.json
```

Это реальный public in-process prepare/get_docs_context, CPU pinned MiniLM,
настоящие retrieval/storage/structural hydration/source checks; НЕ installed
stdio, НЕ client, НЕ semantic acceptance. PYTHONPATH использует текущий checkout.
Labels/threshold не подменяют scoring. Диагностический режим явно keep-all и
`calibration_status=diagnostic_unverified`, `context_quality.status=unverified`.

Расширены исходные authored guide/other documents существующего probe:
длинное ancestor introduction для full-fit regression и 912-token own body с
конечным обязательным условием. Не используются T01/его scores.

| Метрика | V1 | V4 |
|---|---:|---:|
| Units | 9 | 9 |
| Model pairs | 26 | 11 |
| Forwards | 9 | 9 |
| Model input tokens | 5571 | 3837 |
| Inference seconds | 0.7693 | 0.3794 |

Пять full-fit witnesses: Selected, Tail, Noise, Limits, Notes — 4→1 pair каждый.
Длинный own body обработан окнами, полный token coverage query/body/ancestor
проверен по фактическим интервалам, конечное условие доставлено дословно.
Оба конечных пакета одинаковы по source path/text/lines/scope/hash. Проверены
tail condition, continued footnote, remote condition и signed isolation
certificate; every row равен exact source line slice, canonical hash независимо
пересчитан. Scope=project, authority=source_of_truth, project identity присутствует.
Source-file hashes и logical SQLite digest до/после каждого read совпадают.

Успешная попытка: 1 preparation +2 public queries, 37 подтверждённых MiniLM pairs,
18 forwards. Latency сравнение cold V1/warm V4 — не честный cold/warm benchmark;
скорость/semantic экономия на реальных вопросах не заявляются.
Tokenizer предупреждает о 912-token исходном body, но реальные model pairs
ограничены физическим окном 512; source body не усечён.

Предыдущая попытка с теми же CLI args, но work-dir/output `...public-01`,
завершилась assertion failure после первого public query: isolated_service
очищает DOCATLAS env, а новый probe устанавливал flags до входа в него. Это
ошибка harness, не product FAIL. Минимальные flags перенесены внутрь isolated
service, raw packet теперь сохраняется до assertions. Повтор обоснован этим
исправлением. Первая попытка: 1 prepare +1 public query без minimal observer;
raw scoring counts не сохранены, дополнительные model calls не приписываются
нулю без receipt. Всего две попытки: 2 prepares,3 public queries.

Portable receipts в этом каталоге: `receipt.json`, обе `complete-*.json`.
Prepared project/state успешной попытки остаются в `/tmp/opencode/...public-02`.

## EXIT: фактический blocker

```sh
/tmp/opencode/step10-v3-py313/bin/python eval/blind_project_context/step10-fit-correction/exit_feasibility.py > eval/blind_project_context/step10-fit-correction/step10-exit-feasibility.json
```

Credential provider huggingface_hub.get_token(): credentials absent (значения
credentials не выводятся). Pinned base config GET: HTTP401. Pinned snapshots не
найдены в configured/default HF cache и HF-layout directories под /tmp/opencode;
дополнительный config metadata scan под /tmp/opencode не нашёл Gemma base/adapter.
Это ограниченный поиск, не доказательство отсутствия произвольно переименованных
весов на всех дисках. Первый dry check сохранён также в
`/tmp/opencode/step10-exit-feasibility.json`; второй расширил cache metadata search.

Base `google/gemma-2b-it@96988410cbdaeb8d5093d1ebdc5a8fb563e02bad` gated,
adapter `doubleyyh/exit-gemma-2b@e286ce9096178a4aefb743d0919705250fdf1b23` открыт.
RTX5070Ti 16303MiB, driver595.84 обнаружена; текущий torch2.10.0+cpu,
transformers4.57.1, PEFT/Accelerate отсутствуют. CUDA compatibility и classifier
smoke НЕ проверялись: base недоступна. 0 downloads,0 EXIT inference,0 license
acceptance. Новый runtime не создавался, прежние envs не перезаписывались.
English-only/cross-lingual limitation EXIT остаётся отдельным quality blocker.

## Dataset и structural design

`../step10-multidoc-gate/`: 4 проекта ×7 документов,16 вопросов,81 исходная
fact quote,4 no-answer; agent-authored synthetic. `audit_draft.py` проверил
inventory/roles/quotes/scopes и создал draft labels/hash manifest без production
imports, preparation или inference. Это metadata consistency check, не тест
продукта. Источники и разметка требуют parent review; frozen_before_inference=false.
50% reduction — критерий экспериментальной серии, не runtime quota.

Structural v2 описана отдельно, НЕ реализована: semantic body seed не выбирает
subtree; explicit full-section requests обязаны сохранять детей. Natural-language
full-section binding, EXIT Markdown segmentation и anchor-navigation amplification
остаются открыты до review. Подробные endpoints/consumers перечислены в дизайне.

## Отдельная клиентская correction по доказательству родителя

В `run_gap_agent_study.py` вопрос передаётся через `subprocess.run(input=...,
text=True)`, удалён positional question argv; stdout/stderr streams прежние.
Новые plan manifests имеют `question_transport=cli_stdin_exact`.
Основание — сохранённые parent receipts `step10-client-question-audit/receipt.json`
и `step10-client-question-stdin/receipt.json`: OpenCode2.2.5, scripted local HTTP
provider, positional FAIL/API PASS/stdin PASS. В исторической сессии буквальные
кавычки уже были в user message до модели; Terra не является установленной причиной.
Новые transport/provider calls не делались. Подмена внешнего provider транспорта
доказывает client serialization, но НЕ Terra fidelity/конечное качество.

Audit/analysis artifacts родителя не изменялись. Terra/full suite не запускались.
Default off, semantic acceptance открыта, реализация classifier/closure v2 ждёт review.

Финальные статические проверки: AST parse всех 7 изменённых/новых Python-файлов
PASS (без runtime imports); targeted `git diff --check` PASS для tracked diff.
Untracked исходники отдельно охвачены AST parse; git diff не является проверкой
их содержимого. Frozen policies и structural v1 оставлены на прежних ветках
dispatch по code review, полный исторический inference повторно не запускался.
