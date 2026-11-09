# Q6: контекст раздела внутри обычного joint selector

Дата фиксации: 10 ноября 2026. Исходная `main`:
`420e21924e486a7ebca8f4aa891cc176e07280f6`.
Поручение владельца: продолжить работу от `main` и создать PR.

## Вопрос и граница воспроизведения

Вопрос дословно взят из предоставленного владельцем отчёта:

> How does OpenCode compact delivery work, what size limits apply, and how is a delivery failure diagnosed?

Это новый запуск уже объявленного воспроизведения. Старый локальный коммит
`2a65fec`, его `probe.py` и полные трассы отсутствуют в опубликованном
репозитории и в текущей рабочей среде. Тождество прежнему запуску с 256
кандидатами проверяется по наблюдаемым параметрам, но не предполагается.
Это также не точное воспроизведение более раннего вопроса с 86 кандидатами.

## Неизменные входы и критерий

- Копируются все 19 документов текущего `docatlas.project-docs.yaml`, сам
  каталог, исходные bytes, descriptions, scope, module_path и authority.
- Работа идёт в отдельном подготовленном проекте и member store. Источники
  и логическое состояние SQLite сверяются до и после чтений.
- Вопрос, retrieval, source qualification, pool pruning, группировка,
  MMR/cost, eligibility и окончательная упаковка сохраняются.
- Лимит обычного профиля остаётся
  `max(o200k_tokens, ceil(UTF-8 bytes / 4)) <= 12000`.
- `minimal`, Context Links и section compression выключены. Нет новых
  lookup queries, словарей, document bonuses, порогов по известному ответу
  и переинтерпретации `admission_only` или `qualified`.
- Четыре независимые исходные цитаты записаны в `oracle.json` до вызовов.
  Родитель проверяет их только в фактически доставленных и сверенных
  source rows. Worker/scorer не читает oracle.
- Успех Q6 требует все четыре правила, включая формулу и её применимость
  одновременно к compact output и canonical fallback. Повышенный score,
  число 12000 в другом месте, retrieval hit или selected flag недостаточны.

## Однократное ограниченное сравнение

1. `lexical`, с пассивным observer: исходный production selector.
2. `lexical`, без observer: побайтная parity конечного MCP reply, включая
   ссылки и continuation, на том же store.
3. `mini`: существующий joint MiniLM по snippet, историческое truncation512.
4. `body`: тот же pinned MiniLM через существующий complete fit-first scorer,
   только исходный snippet. Это контроль устранения truncation.
5. `contextual`: тот же fit-first scorer, исходный snippet и проверенный
   структурный контекст его раздела (заголовки и собственные введения предков).

`body` и `contextual` — явные исследовательские реализации ранжирования
в отдельном worker. Остальные реальные компоненты установленного пакета
не подменяются. Это installed public stdio MCP с экспериментальным scorer,
а не acceptance нового production default. Никакого replay сериализованных
capabilities вместо живого source check.

Все semantic варианты используют sigmoid(MaxP raw logit), чтобы сохранить
шкалу существующего joint semantic hook. Контекстный score не становится
query credit, допуском источника или свидетельством полноты ответа.
Каждый контекстный span обязан пройти существующую проверку живого источника.
Произвольное чтение файла или доверие одному `raw_document` недопустимо.

Перед сравнениями сохраняются хеши wheel, всех installed product files,
корпуса, сценария и oracle. Полный checked pool фиксируется для каждого
варианта; его изменение делает сравнение несопоставимым. На malformed
configuration/source/model provenance — явный отказ, а не скрытый fallback.

## Regression и stop rule

После локального успеха одного semantic варианта — ограниченное сравнение
его с baseline на опубликованных `eval/main_flow_comparison/questions.json`
Q1 и Q9 и на T01-en из `eval/blind_project_context/questions.json`.
Ожидания берутся из уже опубликованных source quotes, до этих вызовов.
Это development controls; тождество прежним локальным Q1/Q9 не установлено.
Они не доказывают общий recall или качество при исчерпании бюджета.

Номер Q10 неоднозначен: опубликованный main-flow Q10 имеет документированный
ответ и не может подменять упомянутый владельцем исторический no-answer Q10.
Без точного исходного вопроса его результат будет NOT RUN, не PASS.

При отрицательном результате сохраняется исследовательский PR с отчётом и
воспроизводителем; production default не меняется. Повтор допустим только
для конкретного дефекта harness/реализации с сохранением первой попытки.
Нет перебора thresholds/weights до получения PASS.

## Runtime и учёт

Свежий non-editable wheel, Python3.12, frozen core dependencies из `uv.lock`.
Локальный pinned mMARCO MiniLM revision
`1427fd652930e4ba29e8149678df786c240d8825`, все шесть asset SHA256 из
`experimental_selection_modes.py`; CPU FP32, torch2.10.0+cpu,
transformers4.57.1, tokenizers0.22.2, safetensors0.8.0.
Загрузка assets — отдельная явная preparation. Во время MCP сервер offline,
`local_files_only=True`, `trust_remote_code=False`; исходные документы
не передаются внешней модели.

План основных вызовов: 1 `prepare_docs` и 5 `get_docs_context`, 0 resource
reads, плюс initialize/list-tools по фактическому журналу. Regression при
успехе: ещё 6 context calls на том же подготовленном store. Counts включают
неуспешные попытки; model pairs/forwards/tokens учитываются отдельно.
Provider calls, Qwen/CUDA, answering model и реальный клиент OpenCode не входят
в опыт. Размер MCP text — не billed tokens и не стоимость диалога.

## Историческое сравнение

Контекстное оценивание не объявляется новым общим алгоритмом. Уже доступны:

- `eval/opencode_compat/SEMANTIC_SIGNAL_EXPERIMENT_RU.md` и
  `HYBRID_SIGNAL_EXPERIMENT_RU.md`: joint mini/hybrid, регрессии.
- `eval/blind_project_context/step10-selection-audit/RESULTS_RU.md`:
  MiniLM плохо ранжирует нужный T01 даже с контекстом; encoding проверен.
- `eval/blind_project_context/step10-qwen-validation/RESULTS_RU.md`:
  Qwen38/41, потеря связанных weather conditions.
- `eval/blind_project_context/step12-live-comparison/RESULTS_RU.md`:
  one-hop восстановил delivery 19/19 на трёх Meridian-вопросах, но не все
  конечные ответы; четвёртый one-hop вопрос завершился CUDA OOM.

Новый опыт изолирует роль входа ранжировщика в обычном joint pipeline на
данном вопросе и бюджете. Чужие корпуса, метрики и model runtimes не
смешиваются с ним в одну таблицу качества.

## Уточнение после первого baseline, до semantic inference

Первый настоящий MCP read завершился успешно. При неизменной `main`,
`DOCATLAS_MCP_TEXT_FALLBACK=1`, `DOCATLAS_MCP_COMPACT_TEXT=1`, compression off
и default adaptive Assembly доставлены **4/4** требуемых факта: 62 source rows,
9939 o200k tokens, 40285 UTF-8 bytes. Checked pool содержит 256 строк.
Следовательно потеря 2/4 из предоставленного отчёта на этом профиле **не
воспроизведена**. Успешный baseline не объявляется эффектом нового scorer.

Первичная parent-проверка остановилась уже после получения ответа: snapshot
для некоторых источников содержит `snippet` как metadata-словарь. Hash этого
словаря проверялся верно, но последующая проверка строкового вхождения вызвала
TypeError. Raw response, source/SQLite before/after и ledger сохранены.
Исправляется evaluator с offline rescore; продуктовый вызов не повторяется.

До дальнейших inference дополняется диагностический план: после compact
observer parity сделать один baseline с `--profile canonical` (тот же
`DOCATLAS_MCP_TEXT_FALLBACK=1`, compact flag отсутствует, compression off).
Это штатный существующий профиль, который задаёт исходный helper.environment;
его проверка объясняет влияние формы доставки. В исходном сообщении нет
полного environment прежнего probe, поэтому совпадение любого результата
не доказывает точное воспроизведение прежнего локального запуска.

Semantic lanes сравниваются только внутри явно указанного одного профиля
с одинаковым checked pool и 12000. Если canonical воспроизведёт потерю,
именно для него выполняются `mini`, `body`, `contextual` и canonical
observer parity. Compact baseline сохраняется отдельным контрольным фактом,
не смешивается с canonical в оценке эффекта scorer. Дополнительный бюджет
уточнения:2context calls (canonical baseline и parity); подготовка одна.

Сравнение `mini` с `body` проверяет всю fit-first recipe: кроме полного
покрытия длинного входа, отличаются batching и реализация sigmoid. Чистое
сравнение роли контекста — только `body` против `contextual`.
