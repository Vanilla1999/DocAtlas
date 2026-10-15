# Продолжение исследования DocAtlas: сопоставимый selection → answer эксперимент

## Задача

Продолжи уже выполненное исследование и получи обоснованный ответ: можно ли восстановить полезный контекст дешевле экспериментального B1 с помощью mMiniLM, и нужна ли затем XProvence pruning. Нужен реальный сопоставимый эксперимент до конечного ответа, а не ещё один обзор или повтор всех моделей.

Сначала используй сохранённые результаты. Не начинай прежнюю работу заново. Завершение нового этапа — решение по измерениям либо конкретный технический blocker с сохранёнными результатами, не план вместо разрешённого исполнения.

## 1. Обязательный контекст

Repo: `/tmp/opencode/docatlas-compact-review`.
Ожидаемая ветка: `fix/main-flow-compact-evidence`.
Исходный HEAD: `4849b8f796d9e3e25e2c49e58562ec6859978411`.
Предыдущие артефакты: `/tmp/opencode/docatlas-review-evidence/admission-full-20261012/`.

Прочитай AGENTS.md, действующие checkpoint-ограничения и следующие файлы предыдущего этапа:

1. `RESEARCH_METHOD_AUDIT_RU.md` — главное методическое исправление.
2. `COMPACT_CHECKPOINT_RU.md`, `FINAL_REPORT_RU.md`, `G_FINAL_REVIEW.md`.
3. `COMPARISON_PROTOCOL_RU.md`, `G_ORACLE.md`, `G_FROZEN_ORACLE.json`.
4. `A_PIPELINE.md`, `A_Q31_REMAINING.md`, `C_RERANKERS.md`, `D_XPROVENCE.md`.
5. `FINAL_EXPERIMENT.patch`, `DEFAULT_OFF_PARITY.json`, `B1_COMBINED40.json`, `FINAL_COSTS.json`.
6. Релевантные raw inputs/receipts и runners, на которые ссылаются эти документы.

Проверь текущие branch/HEAD/git status. Четыре прежних незакоммиченных файла — результаты эксперимента, не мусор: original_body_discovery.py, ordinary_body_context.py, literal_context_admission.py, run_extra40.py. Не откатывай их и не применяй сохранённый patch повторно. При изменившемся HEAD установи значимые различия, не приписывай старые результаты новой версии.

Новый каталог: `/tmp/opencode/docatlas-review-evidence/admission-selection-v2/`. Старые receipts не перезаписывать.

## 2. Что уже известно

- B0 доставляет обязательные факты в28/40, B1 в39/40; прежние28 сохранены. Это не оценка40 сгенерированных ответов.
- B1 нарушает четыре прежних relevance negatives, увеличивает DTO примерно6.7× и observed context time примерно20×. Это свойства конкретной реализации, не неизбежная цена candidate delivery.
- Mini/Qwen/XProvence подняли полезные окна Q16/Q46 на rank1. Глобальный scalar cutoff не разделяет наблюдённые Q16-positive и OtherAPI-negative.
- Раньше Mini/Qwen/XProvence работали на native archived windows, а R1 — на расширенных public snippets. Общего end-to-end сравнения не было.
- Q16 semantic answer правильный, strict citation FAIL из-за whitespace. Это не доказательство плохого ранжирования.
- LLML line-closure и короткий SWE smoke не доказали бесполезность соответствующих методов.
- Default экспериментального admission OFF. Внедрение по предыдущим результатам не одобрено.

## 3. Область и разрешения этого этапа

Этот запрос разрешает необходимый изолированный local product/model runtime и реальные вызовы уже настроенного хоста на синтетических evaluation данных в пределах бюджета ниже. Переиспользуй имеющиеся CPU environments и pinned assets. Старый лимит600M не восстанавливается, но новые модели этому этапу не нужны.

Используй mMiniLM и, условно после первого сравнения, XProvence. Qwen, CRAG, LLMLingua и SWE заново не запускай. Не устанавливай CUDA, не скачивай повторно weights, не добавляй новый provider, не передавай приватный корпус. Если существующие assets/runtime/host недоступны, зафиксируй конкретный blocker; замена модели/провайдера — только по отдельному решению.

Не добавлять/не запускать unit-тесты, private-helper/AST/compile checks. Проверки — реальные публичные integration сценарии и независимая оценка конечной выдачи. Не менять frozen вопросы, документы, факты и старые negative expectations ради PASS. Не подменять retrieval/selection/storage/validation mocks. Не добавлять словари под benchmark, скрытые lookup, retries или output repairs.

Default deployment, commit/push/merge/release, новая CI-матрица не разрешены этим запросом. Продуктовые изменения допускаются только в минимальном изолированном experimental пути после фиксации файлов и проверки границы. Не переписывать retrieval/storage/catalog или общий framework.

Бюджет: до1000 настоящих local model forwards, до60 host endpoint requests, до80 оцениваемых public context requests; prepares считать отдельно, не более8. CPU модели последовательно, не более8 threads/model и12GiB RSS/process. До4GiB новых артефактов/зависимостей, без дублирования assets; до2часов runtime этапа без учёта анализа. Это потолки, не цель израсходовать всё. Сначала запиши точный меньший workload. Перед превышением остановись и сформулируй конкретную потребность. Переполненный pool не обрезать молча.

Разрешена одна независимая review-роль: фиксирует oracle/split до просмотра новых outputs и проверяет raw результаты после. Не запускай семь исследовательских агентов повторно. Если делегирование недоступно, явно укажи, что review выполнен тем же исполнителем.

## 4. Сначала заморозить план, данные и критерии

Создай STATE.md и PROTOCOL_V2_RU.md до inference. Укажи вопросы, source hashes, split, ограничения, arms, model revisions, представление контекста, budget и правила решения. Отдели повторение авторского scoring от адаптированного DocAtlas pipeline.

Используй Q16/Q46 и существующие OtherAPI/unrelated/multi-fragment controls как известные диагностические задачи, не holdout. Сохрани прежние corpus/questions/oracle неизменными.

Для выбора размера отбора и проверки переноса подготовь небольшой отдельный корпус независимых синтетических документов: ориентир6 calibration вопросов и8 holdout, включая multi-fragment ответы, отрицания/условия и all-irrelevant cases. Не парафразы Q16/Q46, не только замена имён в прежнем корпусе. Calibration и holdout разделять по исходным документам/семействам задач. Oracle берётся из источников независимой review-ролью. Она фиксирует hashes/split до model outputs; holdout labels не используются для выбора параметров. Никаких тысяч скрытых вариантов.

Минимальные критерии на проверенном срезе:
- не потерять ни одно полное обязательство, которое доставляет сопоставимый control;
- не допустить источник, запрещённый scope/version/hash/access правилами;
- не получить unsupported affirmative answer на all-irrelevant вопросе;
- измерить семантику ответа, поддержку отношений/владельца и точность цитат раздельно;
- сохранить CURRENT_CONTRACT verdict для прежних empty-source negatives независимо от отказа хоста;
- оценивать выгоду только после качества, по всему ходу, а не одному сокращённому snippet.

Ноль ошибок на маленьком holdout не доказывает production safety; цель — следующий инженерный выбор.

## 5. Одна граница кандидатов для всех конкурирующих arms

Найди минимальный публичный experimental extension point до topical veto и до расширения/snippet packing. Через настоящие компоненты получи один source-policy-valid native pool на вопрос. Сохрани complete candidate IDs/order/text/hash/span/owner/scope/version/generation, исключения и omissions. Хеш текста сам по себе не доказывает policy-validity.

Все arms получают одни и те же question/candidate bytes и upstream order. Нельзя Mini давать короткие native windows, а control — расширенные snippets, и называть это чистым эффектом ranker. На каждом arm должны действовать одинаковые downstream source validation и presentation правила.

Если этой общей точки нельзя достичь в минимальном разрешённом scope, останови claim end-to-end comparison. Replay можно сохранить как диагностику, но не использовать вместо обещанного публичного результата.

## 6. Первый приоритет: mMiniLM

Сравни три необходимые ветви:

- **B1-control:** существующая experimental candidate delivery без нового ranker.
- **Budget-control:** тот же pool, существующий порядок, ограниченный отбор по общему правилу бюджета.
- **Mini:** тот же pool и тот же бюджет/packing, но порядок mMiniLM.

Budget-control нужен, чтобы не приписать модели экономию от простого сокращения выдачи. Если прежние доказательства полностью соответствуют input/code/presentation новой ветви, переиспользуй их; иначе объясни необходимость свежего вызова.

Используй сохранённый официальный checkpoint mMARCO mMiniLMv2, FP32 и его query/document scoring. Не интерпретировать score как вероятность правильного ответа. Не ставить arbitrary0/.5 threshold.

Заранее объяви небольшой выбор operational budget, например k∈{1,2,4}; выбери минимальный достаточный только на calibration, проверяя совокупные факты нескольких фрагментов. Для Budget-control и Mini используй один зафиксированный budget и одинаковые правила обработки длины/дубликатов. Сохрани все scores единственного scoring pass. Не менять budget после holdout и не подбирать его по Q16/Q46.

**Ranking и abstention — разные задачи.** Top-k может вернуть нерелевантный текст; честный отказ хоста не чинит старый empty-source контракт. Не добавляй тайком sufficiency judge как бесплатный veto. Если для сохранения контракта нужен дополнительный selector/evaluator, это отдельная гипотеза/ветвь с отдельной стоимостью и обоснованием; текущий arm получает соответствующий FAIL.

## 7. Общая передача источников и цитирование

Хост во всех сопоставимых arms должен получать одинаковую структуру: исходный вопрос, выбранные дословные fragments, IDs и реальные bound metadata, необходимые для owner/path/scope/version attribution. Не удаляй public provenance под предлогом защиты от oracle leakage: обычные метаданные источника не являются эталонным ответом. Золотые spans/facts, private diagnostics, scores других arms и чужие ответы хост не получает.

Для первого ranking сравнения сохрани единый frozen generator prompt/формат цитирования; его прежний citation FAIL учитывай отдельно от semantic correctness. Если заранее меняешь общий формат presentation, новая baseline должна использовать его тоже, а старые host ответы не считаются парным comparator.

Проверяемое извлечение цитат по выбранному source/fragment ID или координатам — отдельная небольшая delivery adaptation. Она может извлечь точные bytes и отвергнуть недопустимые ссылки, но не должна незаметно исправлять модельный ответ или добавлять пропущенные факты. Сохраняй исходный ответ до обработки и отдельно вердикты text equality и claim support. Не смешивай улучшение citation adapter с эффектом ranker. Не переписывай прежние raw ответы/FAIL.

Один уже настроенный host alias, одинаковые доступные settings, чистый независимый request на case/arm, одна попытка. Сохраняй окончательный реально отправленный prompt, включая transport wrapper. Нераскрытые backend revision/sampling/tokens/billing отмечай UNKNOWN; не обещай детерминизм и exact paper reproduction.

## 8. Второй приоритет: XProvence, только обоснованный paired experiment

Переходи сюда, если после первого этапа остаётся существенный избыток контекста и есть бюджет проверить его сокращение. Не запускать автоматически ради заполнения таблицы.

- **X-rank:** тот же исходный pool, тот же зафиксированный selection budget, XProvence order, исходные selected windows без pruning.
- **X-prune:** ровно те же selected IDs/order, pruning из того же joint forward. Меняется только retained content/presentation gaps.

Используй pinned author implementation с заранее явными threshold/sentence-rounding semantics. Не выдавай HF-code rounding за другую формулу из статьи. No threshold sweep по holdout. Реконструируй отдельные exact source spans; не выдавай decoded склейку за непрерывную цитату.

Сохраняй реальные заголовки/владельцев/условия по заранее общему структурному правилу, не по oracle rescue. Стоимость closure и source metadata включать полностью. Невозможность корректно привязать source span — BLOCKED/FAIL, не fabricated envelope. Дай одному и тому же хосту оба пакета и независимо проверь факты, связи, цитаты и стоимость. Учитывай ранее установленные ограничения использования конкретного checkpoint при рекомендации внедрения.

## 9. Измерения и остановка

Для каждого вопроса/arm сохраняй: hashes/revisions, полный pool, selected/dropped IDs/spans, scores, фактический public payload и host input, raw answer, семантический verdict, exact-citation verdict, unsupported claims, source-policy/current-contract результаты, вызовы, ошибки и длины.

Стоимость: source acquisition/selection/packing + resident ranker/pruner processing + source reconstruction + host. Cold load отдельно, не добавляй загрузку весов к каждому production запросу и не скрывай её. Для сравнительных timings не запускать competing workloads параллельно; один проход — наблюдение, не p95. DTO tokens, model tokenizer counts, submitted prompt proxy и billing — разные столбцы. Не сравнивать CPU ratios с GPU claims статьи.

Не переполучать одинаковый pool ради каждой модели, если reusable public experimental execution корректно сохраняет реальные policy/validation границы. Reuse должен быть доказан, не объявлен. Не повторять успешные наборы без новой причины. Failed attempts и recovery учитывать, не вычитать из бюджета.

После серьёзного source-policy defect останови соответствующую ветвь. После двух неудачных patch→integration циклов одного дефекта остановись с конкретным blocker. Нельзя бесконечно добавлять эвристики или перегенерировать до PASS.

Полную frozen50 регрессию не запускать для каждой модели автоматически: сначала узкий сопоставимый срез, затем одна необходимая регрессия затронутой product path при перспективном результате. Новое независимое quality сравнение не заменяет сохранение прежних успешных сценариев.

## 10. Финальный результат

Создай `RESULT_V2_RU.md`, машинно-читаемую таблицу и независимый review. Начни с одного решения:

1. Mini даёт измеримую пользу сверх одинакового budget-control и B1 — продолжить этот путь;
2. XProvence pruning добавляет пользу сверх своего ranking-only control — перспективен следующий этап;
3. Дешёвого budget-control/хоста достаточно на проверенном срезе — модель не оправдана здесь;
4. Данных недостаточно/есть конкретный blocker — указать, какое единственное сравнение отсутствует.

Таблица: arm | одинаковый pool/граница | independent cases | полные факты | semantic answers | grounded relations | exact citations | false positives/refusals | CURRENT_CONTRACT | policy violations | calls/tokens/time/RSS.

Отдельно объясни, чем обусловлен результат: ranking, просто меньший budget, presentation, citation adapter, pruning или ошибка хоста. Не объявлять непроверенный метод проигравшим; FAIL нашего строгого контракта не равен опровержению статьи. Отличай выполненное диагностическое исследование от обоснованного выбора production решения. Приложи точные команды/артефакты и перечисли незакрытые ограничения.
