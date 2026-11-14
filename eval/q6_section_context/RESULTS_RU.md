# Q6: профиль доставки и структурный контекст MiniLM

10 ноября 2026. Ветка создана непосредственно от `main`
`420e21924e486a7ebca8f4aa891cc176e07280f6`.

## Что установлено

**Потеря зависит от профиля доставки.** Неизменённая `main` доставляет все
четыре проверяемых правила в compact/adaptive, но только два в canonical.
У этих запусков полностью одинаковы acquisition, checked source pool,
source snapshots и query plan. Профиль меняет представление, стоимость
пробного пакета и состав помещающихся в него источников.

Это не исправление нового ранжировщика и не доказательство, что прежний
отчёт ошибочен. В старом сообщении нет полного environment, а его локальная
ветка и raw artifacts не опубликованы. Здесь воспроизведён класс потери на
дословно том же объявленном вопросе, 19 документах и 256 кандидатах;
тождество старому локальному исполнению не установлено.

Производственный код, конфигурационные defaults, dependencies, документы и
каталог не изменены. PR содержит воспроизводитель, экспериментальный scorer,
проверяемые данные и разбор. Никакие scores не становятся source permission,
query coverage или доказательством полноты.

## Условия

Вопрос:

> How does OpenCode compact delivery work, what size limits apply, and how is a delivery failure diagnosed?

Все 19 документов и оригинальный `docatlas.project-docs.yaml` взяты из
исходной main с сохранением bytes, descriptions, project/module scope и
authority. Их SHA-256 записаны до первого вызова и перенесены в
`FREEZE_MANIFEST.json`. Весь опыт использует один изолированный подготовленный
проект и member store. Установленный non-editable wheel сверён с checkout:
**457 файлов, включая 441 Python modules; расхождений 0**.

Оба профиля: `DOCATLAS_MCP_TEXT_FALLBACK=1`, section compression off,
обычные admission/retrieval/pruning/MMR и прежний лимит 12000. `compact`
дополнительно включает `DOCATLAS_MCP_COMPACT_TEXT=1` с default adaptive
Assembly. В `canonical` compact flag отсутствует. Ни minimal/50000, ни
Context Links, ни векторный поиск не включались.

Здесь `canonical` означает обычный JSON-профиль с выключенным compact flag.
Это не искусственно вызванный fallback после ошибки compact renderer:
поведение такой ошибки отдельно не исполнялось, проверялась доставка
документированных правил о ней.

Критерии — четыре дословные source quotes в `oracle.json`:

1. `max(o200k_tokens, ceil(UTF-8 bytes / 4)) <= 12000`.
2. Применимость этого правила одновременно к compact output и canonical
   fallback, в пределах указанного исходником ordinary profile.
3. Условия ошибки `context_delivery_unavailable`, `isError=true`,
   `retryable=false`.
4. Ошибку доставки нельзя трактовать как отсутствие документации,
   повторять неизменный вызов, расширять scope или считать grep из dump
   успешной MCP-доставкой; до retry требуется исправить host/delivery.

Worker/scorer не читает oracle. Родитель оценивает реальные source rows
из `content[].text` после вызова, проверяя source bytes, диапазоны строк,
scope/authority/version и binding hashes. Проверка покрытия этих четырёх
цитат не является оценкой всех аспектов вопроса или конечного ответа модели.

## Реальная доставка

| Профиль | Ранжирование | Факты | Source rows | o200k tokens | UTF-8 bytes |
|---|---|---:|---:|---:|---:|
| compact/adaptive | исходный lexical | **4/4** |62|9939|40285|
| canonical | исходный lexical | **2/4** |39|11895|40067|
| canonical | существующий joint MiniLM | **2/4** |10|3282|11593|
| canonical | fit-first MiniLM, только исходный фрагмент | **2/4** |10|3289|11593|
| canonical | fit-first MiniLM + структурный контекст | **2/4** |10|3283|11593|

Все приведённые MCP ответы прошли прежний
`max(o200k_tokens, ceil(UTF-8 bytes / 4)) <= 12000`.
Для compact максимум двух мер составляет 10072. Нельзя сравнивать только
bytes: canonical упирается в токены раньше byte ceiling.

В двух lexical профилях выполнены отдельные observation on/off calls:
**raw MCP replies совпали полностью**, включая source references и
continuation. Поэтому улучшение compact не объясняется пассивным recorder.

## Где теряется формула

В каждом наблюдаемом Q6 вызове зарегистрированы две acquisition execution
по 256 кандидатов. Целевой фрагмент `docs/opencode-compact-text.md:60–71`
находится на 17-м месте в обеих трассах. Его `routing_only=false`: совпадения
есть и в body, и в catalog description. Нельзя описывать этот случай как
потерю сигнала, существовавшего исключительно в описании документа.

Source-valid pool содержит 256 строк. Обычный body-pruning оставляет 101 строку
из 29 разделов. Целевой фрагмент остаётся в нём; source qualification —
`source_valid_relevance_unassessed`, без придания answer coverage.

В lexical compact выбран весь трёхстрочный раздел 38–71 после 59 уже выбранных
строк, итог 62. Relevance раздела 0.4200468701, redundancy 0.2052397176,
стоимость 4074 bytes. В canonical тот же раздел рассматривается после 39 строк
и получает `delivery_budget`. Затем отдельный нужный фрагмент также не
проходит rendered-packet budget: relevance 0.2891357083, redundancy 0.1595007266.
Это потеря при упаковке, а не source denial, retrieval miss или pruning.

`joint_context_selection._delivery_fits` использует выбранное представление
внутри каждого fit trial: standalone/Assembly при compact либо canonical JSON.
Сам Assembly не придумывает и не сокращает цитаты. Однако вызов renderer
из selector влияет на число источников, помещающихся в окончательный пакет.

Дополнительный offline контроль: тот же сохранённый промежуточный пакет из
62 строк при canonical serialization занимает 65389 bytes, больше 48000. Это
не новый canonical MCP ответ, а объясняющий размерный расчёт по сохранённым
данным. Для принятия вывода использованы настоящие оба MCP профиля.

## Что показали semantic controls

Используется только локально подготовленный pinned mMARCO MiniLM v2,
revision `1427fd652930e4ba29e8149678df786c240d8825`. Все шесть asset hashes
проверены. CPU FP32, torch2.10.0+cpu, transformers4.57.1,
tokenizers0.22.2, safetensors0.8.0. Сервер offline; документам не требовалась
отправка на внешний endpoint.

Существующий `mini` оценивает snippet и применяет sigmoid. Нужный фрагмент
получил 0.0003814346; max score его раздела 0.0019261700, redundancy 0.1442593225.
Раздел исключён с `nonpositive_gain`, **до проверки размера**, при свободном
бюджете. Сокращение ответа до 3282 токенов не является исправлением полноты.

`body` использует существующий complete fit-first scorer без structural
context. Все 101 пары целиком помещались в окно; максимальная длина 358 токенов.
Для цели:216 body +23 question +4 special =243. Его score 0.0003814364 почти
совпадает с existing mini. Выбраны те же 10 исходных строк; единственное
различие packet — configuration-bound continuation fingerprint. Его иная
токенизация объясняет 3282→3289 при одинаковых bytes и исходном содержимом.
Усечение input не объясняет потерю этого фрагмента.

`contextual` сохраняет неизменный checked row и добавляет source-exact
заголовок и собственные введения предков. Каждый применённый context span
проверяется через текущий native derivation receipt и каноническую
qualification. Scorer не читает дополнительные файлы, не добавляет источники
в выдачу и не меняет qualification. Агрегация раздела остаётся max по его
окнам: это **оценка фрагментов со структурным контекстом**, не holistic
оценка всего раздела одним входом. Соседние собственные окна раздела не
добавляются к каждому target.

Контекстный вариант также не восстановил формулу. Её sigmoid score вырос
с 0.0003814364 до **0.0420689882**, raw logit — с −7.8711848259 до −3.1254649162.
Она стала сильнейшим окном собственного раздела, но его relevance всё ещё
ниже redundancy 0.1442593225. Решение снова `nonpositive_gain`, а не отказ
по бюджету. Все три semantic варианта выдали **одни и те же 10 source rows**.

Для целевого окна использованы 111 source bytes: исходный заголовок документа
на строках 1–2 и заголовок собственного раздела на строке 36. Полная пара
составила 280 токенов: 23 question + 216 body + 37 context + 4 special. Условия
применимости и сама формула целиком присутствовали во входе ранжировщика.
Contextual score строки 74–81 с правилами ошибки — 0.9739773815, соседних
строк 38–46 и 47–59 — 0.0010082220 и 0.0031627543. Это не одинаковая прибавка
всем фрагментам документа, но и не успешный отбор обязательных фактов.

Независимо проверены 101 scored row, 221 context span, их hashes, исходные
границы и восстановленный concatenated context. Из token intervals
пересчитаны 296 пар и 85018 input tokens; покрыты все query/body/ancestor
tokens, пропусков интервалов нет, каждая пара ≤512. 28 units потребовали
нескольких окон, максимум 10; target помещался целиком.

Чистое сравнение роли контекста — `body` против `contextual`. `mini` против
`body` дополнительно отличается batching, sigmoid и обработкой длинного
входа; роль усечения установлена отдельно по сохранённым token intervals.

## Расход и решение после опыта

Выполнено **8 продуктовых вызовов: 1 подготовка и 7 чтений контекста**.
Дополнительно учтены 7 server processes, 7 MCP initialize и 7 list-tools.
Resource reads и answering-model/provider calls — 0. В пяти observed runs
записаны 10 внутренних acquisition executions; не записанные внутренние
операции двух plain calls не выдаются за измеренные.

| Semantic вариант | Model forwards | Scored pairs | Model input tokens | Время context call |
|---|---:|---:|---:|---:|
| existing mini |7|101¹|не записаны|51.326 с|
| body fit-first |101|101|15567|146.514 с|
| contextual fit-first |101|296|85018|153.683 с|

¹Для existing mini 101 пара следует из одной query lane и 101 реально
оценённой строки; исторический receipt записывает 7 forwards, но не
`model_pairs` или `model_input_tokens`. Общий подтверждённый счётчик
forwards — 209; сумма записанных input tokens 100585 покрывает **только body
и contextual**, а не все три варианта. Недостающие значения не заменялись 0.
Время включает холодную загрузку/проверку локальной модели и MCP обработку;
это единичные наблюдения, не latency benchmark. Загрузка assets и сборка
окружения в эти времена не входят.

Поскольку ни один новый semantic control не достиг 4/4, предусмотренный
следующий regression gate Q1/Q9/T01 не запускался. Его frozen вопросы и
цитаты включены для повторения после отдельного успешного кандидата;
**PASS по ним здесь не заявляется**. Исторический no-answer Q10 также
NOT RUN: однозначного исходного вопроса нет.

**Решение: defaults и production code сохранить.** Данный результат не
обосновывает снятие `admission_only`, увеличение бюджета или подбор весов
MMR под один известный вопрос. Отрицательный результат узкой абляции не
опровергает все возможные способы оценки полезности целого раздела или
набора разделов: такие варианты здесь не реализованы и не проверены.

## Сопоставление с предыдущими работами

Этот эксперимент не представляет contextual MiniLM как новый общий подход.
В [Step10 selection audit](../blind_project_context/step10-selection-audit/RESULTS_RU.md)
он уже недооценивал PR-текст T01, даже когда пара полностью помещалась и
кодирование было независимо проверено. Здесь исследуется более узкое
применение к прежнему joint pipeline и 12k, без minimal acquisition/closure.

[Qwen validation](../blind_project_context/step10-qwen-validation/RESULTS_RU.md)
дала 38/41 факт с потерей weather conditions. Позднейший
[Step12 live comparison](../blind_project_context/step12-live-comparison/RESULTS_RU.md)
с one-hop восстановил delivery 19/19 на трёх Meridian-вопросах, но не все
конечные ответы. Четвёртый one-hop case получил CUDA OOM и не считается
успешным no-answer. Это другая задача и runtime; Qwen здесь не перезапускался
и не подменялся CPU-моделью.

## Ошибка evaluator и границы доказательства

Первый compact MCP call завершился успешно. Parent evaluator затем упал,
потому что четыре snapshot-поля `snippet` содержат metadata-словарь, а
проверка ожидала строку. Digest первоначальной формы был верен; ошибка была
в последующем строковом операторе. Исправление сохраняет исходную форму
для hash и проверяет реально доставленные text bytes отдельно.
Тот же raw response пересчитан offline; новый MCP call не выполнялся.
Первый parent wall time до ошибки не был записан и остаётся `null`.

Проверено: источники и логическое состояние SQLite до/после неизменны;
каждая выданная строка соответствует исходнику, scope, authority и version;
каждый observed source binding проверен; сравниваемые pools идентичны.
Отдельный reviewer независимо разобрал настоящий compact wire стандартным
JSON, без product decoder, и подтвердил 4/4 и 62/62 source spans.

Это **installed public stdio MCP**, в semantic controls — с явно
экспериментальным ranking hook. Это не настоящий клиент OpenCode, не новая
генерация ответа, не general benchmark и не подтверждение всей CI.
Provider usage, качество final answer, стоимость диалога и общий recall
не измерялись. Исторический no-answer Q10 неизвестен и не подменялся.

## Артефакты и повторение

[README](README.md) содержит команды установки и воспроизведения;
[PROTOCOL_RU](PROTOCOL_RU.md) — исходный план и явно записанное уточнение
после неожиданного compact PASS до semantic inference.
Публичный `evidence/` хранит exact source rows, checked pools, lexical
field matches, selector decisions, semantic inputs/scores/token intervals,
provenance и call ledgers. Raw capabilities, environment и абсолютные пути
изолированной среды не публикуются; для raw файлов сохранены hashes и sizes.

`export_results.py --verify evidence` независимо пересчитывает source-fact,
span и hash checks без модели и MCP. Sanitized artifacts не заменяют живую
повторную проверку capabilities; raw-only границы записаны в manifest.
