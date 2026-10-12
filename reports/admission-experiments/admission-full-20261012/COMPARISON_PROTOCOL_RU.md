# Замороженные общие правила сравнения

Дата фиксации: 2026-10-12, до новых model/runtime результатов.

## Область

Устранение потери уже найденных фактов. Не изменять retrieval/storage/catalog и не внедрять новую модель в default. Product patch пока не назначен. Не смешивать relevance-контракт с source-policy.

## Ветви

- B0: текущая публичная выдача, сохранённый current-head baseline.
- B1: тот же retrieval pool, после реальных source-policy guards, до literal topical veto; bounded candidate delivery через изолированный публичный экспериментальный путь. Требует реализации и отдельного утверждения contract delta.
- R1/R2/R3/R5: RankGPT-style, Qwen 0.6B, mMiniLMv2, XProvence ranking на той же policy-valid pool. CRAG — отдельно с явно согласованной correction policy.
- P1: XProvence pruning против собственного no-pruning ranking.
- P2: LLMLingua-2 против идентичного несжатого пакета, не меняя ranker.
- P3: SWE-Pruner на отдельной code-задаче, не агрегировать с documentation questions.
- S1: sufficiency autorater — отдельный диагностический результат, не production veto.

## Честные границы

Saved replay не публичная интеграция. Подмена transport не real generation. Prompted ranking не fine-tuned evaluator. Вызов произвольной модели не точное воспроизведение статьи. Экспериментальная выдача нерелевантных источников может улучшить ответ хоста и одновременно нарушить старый empty-sources negative; сохранять оба verdict.

## Фиксация перед исполнением

- G_ORACLE.md и отдельные G facts фиксируются до patch/scores. Независимый corpus — источник ожиданий.
- HOST_PROMPT_RU.txt одинаков во всех сопоставимых generation ветвях. Хеш, модель/revision, настройки, бюджет и сериализацию записать до вызовов. Один ответ, без best-of/retries; чистая сессия на case/branch.
- Выбор candidate limit и threshold требует заранее выделенной calibration выборки. Q46/Q16 диагностические задачи, не calibration и не holdout. Без calibration сравнивать только ranking/доставку, не заявлять доказанную abstention policy.
- Не передавать генератору oracle, required_facts, private diagnostics, model scores других ветвей и архивные ответы. Только исходный question и настоящий public packet выбранной ветви.
- Порядок ветвей фиксированный B0/B1/R1/R2/R3/R5/P1/P2; порядок вопросов — исходный. Loading/warmup учитывать отдельно. Один GPU — последовательное исполнение, агенты параллельны только в подготовке.
- Пока генератор/provider не указан и не разрешён, число generation calls = 0, generation correctness = NOT RUN.

## Сохранение данных

Для каждого case/branch: question, pool IDs, policy receipts, selected/dropped IDs/spans, scores, public packet, точный model-visible input, ответ, цитаты, independent verdict; SHA/revision/prompt hash/device/precision; input/output tokens/calls/latency/memory/errors/truncation.

Нельзя объявлять sources проверенными на policy только по валидному hash. Для B1 требуются реальные receipts существующих access/consent/scope/version/catalog/generation guards. В архиве пропущенный guard = UNVERIFIED, не PASS.

## Критерий решения

Сначала отсутствие source-policy нарушений, затем полные факты/grounded correctness/false positives и false negatives, затем ресурсы. Не суммировать неоднородные code/documentation задачи. Если преимущества не измерены, рекомендовать следующий минимальный эксперимент, не победителя и не deployment.

## Ограничения запуска

No unit tests. Existing CI targets перед новым вызовом классифицировать по реальной границе. No local product/model runtime, imports, installs и weights downloads до явного снятия соответствующих checkpoint запретов. Независимый анализ продолжается; эксперимент не имитируется.
