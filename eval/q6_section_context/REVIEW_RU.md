# Независимая проверка опыта Q6

## Вывод

**Числа и отрицательный результат semantic controls подтверждены.** На
неизменённом production-коде `420e21924e486a7ebca8f4aa891cc176e07280f6`
compact/adaptive доставил 4/4 зафиксированных факта, canonical lexical —
2/4. Existing MiniLM, fit-first body и fit-first contextual также дали 2/4.
Добавление структурного контекста повысило оценку формулы, но не вернуло
её в MCP-ответ. Основания считать это исправлением продукта отсутствуют.

Это отдельный review: reviewer не писал `probe.py`, `oracle.json`,
`contextual_relevance.py`, `export_results.py` или `RESULTS_RU.md`, не
выполнял дополнительные продуктовые вызовы и не запускал модели. Проверены
код, сохранённые полные ответы и трассы, исходные файлы, установленный
пакет и окончательная публичная выгрузка. Для независимого разбора raw
артефактов использована стандартная библиотека Python, без product decoder
и без повторного исполнения source admission.

Основные ссылки: [протокол](PROTOCOL_RU.md), [freeze](FREEZE_MANIFEST.json),
[oracle](oracle.json), [результаты](RESULTS_RU.md),
[manifest публичных данных](evidence/manifest.json).

## Фактические ответы и полный учёт запусков

Каждый сохранённый `response.json` содержит один успешный MCP text block,
дословно совпадающий с соответствующим `wire.txt`. Canonical разобран как
JSON с source rows; compact grouped-table независимо раскрыт по
`source_columns`, `source_groups` и `source_context`. Факты пересчитаны по
доставленным исходным символам, а не по diagnostic fields, score или
внутреннему флагу поддержки ответа.

| Сохранённый запуск | Факты | Source rows | UTF-8 bytes | Записанные o200k tokens |
|---|---:|---:|---:|---:|
| lexical-observed, compact | 4/4 | 62 | 40285 | 9939 |
| compact-plain | 4/4 | 62 | 40285 | 9939 |
| canonical-lexical | 2/4 | 39 | 40067 | 11895 |
| canonical-plain | 2/4 | 39 | 40067 | 11895 |
| canonical-mini | 2/4 | 10 | 11593 | 3282 |
| canonical-body | 2/4 | 10 | 11593 | 3289 |
| canonical-contextual | 2/4 | 10 | 11593 | 3283 |

Проверены все **232 доставленные строки** семи запусков: наличие документа
в frozen catalog, точное вхождение текста в объявленный диапазон строк,
scope и authority из каталога, unversioned binding. Для пяти observed
запусков дополнительно пересчитаны все **131 delivered binding digest** из
исходного snapshot material. Структурные metadata-словари в поле `snippet`
сохранены в исходной форме при вычислении digest и не считаются текстом
доставленного доказательства.

В обоих compact ответах формула и применимость находятся в настоящей
source row `docs/opencode-compact-text.md`, строки 60–71; правила ошибки —
в строках 74–81. В остальных пяти ответах первые два факта отсутствуют,
а последние два доставлены. Покрытие по [oracle](oracle.json) и значения
в [RESULTS_RU](RESULTS_RU.md) совпадают.

Полные raw replies observed/plain для каждого lexical профиля равны,
включая ссылки и continuation. У всех трёх semantic вариантов source rows
полностью одинаковы; единственное различие разобранных MCP packets —
configuration-bound continuation token. Поэтому разные token counts при
одинаковых bytes не означают изменение доставленных исходных фрагментов.

Reviewer независимо пересчитал UTF-8 bytes, hashes и максимум по записанным
token counts и `ceil(bytes/4)`. O200k counts получены установленным
tokenizer в основном опыте; review стандартной библиотекой не повторяет
токенизацию. По этим измерениям все ответы укладываются в прежние 12000,
для compact максимум равен 10072.

## Неизменность источников и сравнимость входов

Проверены SHA-256 всех 19 документов, каталога, oracle и вопроса из
[FREEZE_MANIFEST](FREEZE_MANIFEST.json). Все source manifests запусков
совпадают с freeze. На момент review установленный non-editable пакет
повторно сверен по каждому файлу с checkout и provenance: **457 файлов,
в том числе 441 Python-файл, без расхождений**. SHA-256 wheel совпадает
с frozen значением. Это проверка подготовленной установки и её сохранённой
provenance; она не является отдельной проверкой всех других окружений.

Во всех пяти observed runs напрямую сравнены полные массивы acquisition,
`before.sources`, `before.snapshot` и `before.query_plan`, включая поля,
которые не публикуются. Они равны. Каждый наблюдаемый вызов содержит две
одинаковые acquisition execution по 256 кандидатов; source-valid pool
также содержит 256 строк. Публичные hashes и проверенные pools согласуются
с этими raw данными. Обычный pruning оставляет 101 строку из 29 разделов.

Целевая строка 60–71 действительно найдена на позиции 17, сохранена после
pruning, а её lexical metadata содержит `routing_only=false`. Поэтому
объяснение исключительно совпадением catalog description не соответствует
измеренной трассе. В canonical lexical окончательное решение —
`delivery_budget`; в compact тот же раздел выбран. Статический путь
`_delivery_fits` в
[joint_context_selection.py](../../docmancer/docs/application/joint_context_selection.py)
использует выбранный renderer уже внутри проверки пробного пакета, что
согласуется с различающимся составом итоговой выдачи.

Сохранённое логическое состояние всех шести SQLite-таблиц совпадает до и
после каждого контекстного чтения. Подготовка учитывается отдельно и
закономерно создаёт индекс. Производственные файлы, dependencies, каталог
и исходные документы не изменены; изменения находятся в этом eval-каталоге.

## Изоляция эталона и source proof

В [probe.py](probe.py) worker получает вопрос, режим и настройки записи;
он не читает oracle. Оценка обязательных фактов выполняется родителем
после сохранённого MCP ответа. В [contextual_relevance.py](contextual_relevance.py)
нет чтения source files, expected quotes, поиска по именам целевых
документов или специальных бонусов для Q6.

Body/contextual сохраняют существующие eligibility, pruning, группировку,
MMR и бюджет. Hook изменяет только relevance и фиксирует recipe/mode в
continuation settings; возвращение из контекстного менеджера восстанавливает
заменённые функции. Scores не меняют `qualified`, `admission_only` или
coverage credit.

Для каждого scored row проверяется текущий application-owned native
receipt, совпадение projected source, неизменный body span и SHA-256
исходного документа. Для каждого применённого ancestor/heading span
используется существующая цепочка original-body derivation, canonical
qualification и reference probe. Она соответствует исходному source-only
hydration path и не создаёт дополнительную выданную source row.

Offline review независимо подтверждает исходные bytes, spans, hashes и
согласованность записанных receipts. Сериализованный receipt не заменяет
живую capability; повторный admission здесь не выполнялся. Полная проверка
его действительности относится к сохранённому runtime и повторению опыта.

## Semantic receipt и причина отрицательного результата

Для body/contextual независимо проверены все 101 scored row каждого режима,
исходные body/context spans, их line/character bounds и SHA-256. Для
contextual проверен **221 применённый span** и точное восстановление
concatenated context. Сохранённые sigmoid scores согласуются с raw logits.

| Контроль | Scored rows | Model pairs | Model forwards | Input tokens | Наибольшая пара |
|---|---:|---:|---:|---:|---:|
| body fit-first | 101 | 101 | 101 | 15567 | 358 |
| contextual fit-first | 101 | 296 | 101 | 85018 | 486 |

Из записанных token intervals независимо пересчитаны количество пар и
input tokens, включая special tokens. Для каждой строки интервалы
покрывают все записанные query/body/ancestor tokens без пропусков;
`intervals_omitted=0`, каждая пара помещается в 512. Body целиком помещался
во всех 101 случаях. В contextual 73 строки помещались целиком, 28
использовали несколько окон, максимум 10. Это проверка полноты записанных
интервалов и accounting; модель и tokenizer при review не запускались.

Целевой body содержит 216 model tokens, вопрос — 23, special tokens — 4.
В body полная пара занимает 243 токена; contextual добавляет 37 токенов
из 111 source bytes, итог 280. Это заголовок документа на строках 1–2 и
заголовок собственного раздела на строке 36. Формула и её условия целиком
присутствуют в scored body, поэтому их потерю нельзя объяснить усечением
этой пары.

| Показатель цели | Body | Contextual |
|---|---:|---:|
| Raw logit | −7.871184825897217 | −3.125464916229248 |
| Sigmoid score строки | 0.000381436436767411 | 0.042068988179556066 |
| Relevance раздела | 0.001926170810052058 | 0.042068988179556066 |
| Redundancy раздела | 0.14425932253720256 | 0.14425932253720256 |
| Решение | nonpositive_gain | nonpositive_gain |

Contextual сделал целевую строку сильнейшей в её разделе. Однако при
неизменной текущей функции выбора прирост полезности остаётся отрицательным,
до проверки размера. Бюджет в semantic runs свободен. Вывод ограничен
данным scorer, его шкалой scores и существующей MMR-функцией: он не
доказывает бесполезность всех semantic подходов и не обосновывает подбор
MMR-весов по этому одному вопросу.

Чистая абляция контекста — body против contextual. Existing mini против
body дополнительно отличается batching и способом полного кодирования;
его исторический receipt содержит 7 forwards, но не отдельные счётчики
input tokens/model pairs. 101 query-row pair следует из одной query lane
и 101 scores; неизвестное число input tokens не заменено нулём. Совокупно
записаны 209 forwards, а сумма 100585 input tokens относится только к
body/contextual. Context call contextual длился 153.682784 секунды, body —
146.513886, existing mini — 51.326162; единичные холодные запуски не
образуют сравнение производительности.

## Публичная выгрузка и пределы воспроизведения

После фиксации всех семи запусков reviewer выполнил:

```sh
python eval/q6_section_context/export_results.py --verify eval/q6_section_context/evidence
```

Результат — `VERIFIED_PUBLIC_SOURCE_FACTS` для всех семи наборов с теми же
фактами и количеством строк, без MCP и model execution. Проверены checksums
артефактов, frozen source bytes, source quotes, exported checked/acquisition
pools и их размеры, queries/query-plan hashes, semantic span hashes,
согласованность per-run/aggregate call ledgers и state proof.

Статический review [export_results.py](export_results.py) подтвердил
явный whitelist публичных полей. Исходные цитаты сохраняются дословно и
сверяются с frozen files. Live source/continuation capabilities, environment,
абсолютные runtime paths, полные admission snapshots и raw SQLite state
не включены; для raw файлов публикуются только hashes и размеры.
Детерминированный gzip и отказ от перезаписи существующей выгрузки сохраняют
возможность сравнения артефактов.

Публичная выгрузка позволяет повторить source-fact scoring и проверить
публикуемые spans. Она сама по себе не доказывает подлинность первоначального
MCP transport, live authorization или исполнение модели: для этого нужны
сохранённые raw receipts либо новый явно учтённый runtime. В этом review
полные raw receipts были доступны; эти границы указаны в manifest и не
скрыты за успешным offline verifier.

## Ограничения и решение

Реестр подтверждает **8 продуктовых вызовов: 1 prepare и 7 get context**,
плюс 7 server processes, 7 initialize и 7 list-tools. Source-resource reads
и answer-model calls равны 0. Reviewer добавил только offline чтения.
Первый parent evaluator завершился ошибкой уже после успешного MCP ответа;
его исправление и пересчёт того же raw не являются дополнительным вызовом,
а незаписанное первое время корректно оставлено `null`.

Новый вопрос, корпус и delivery profiles описаны явно. Полного environment
и raw старой неопубликованной ветки нет, поэтому этот опыт не объявляется
точным повтором её 11818-token запуска. Обнаруженный compact PASS и
добавление canonical control отражены отдельным уточнением протокола до
semantic inference.

Q1/Q9 из main-flow и T01 имеют независимо проверенные frozen source quotes,
но regression gate здесь **не выполнялся**: новый semantic вариант не
достиг Q6 4/4. Эти вопросы не выдаются за точно восстановленный набор
предыдущей локальной ветки. Однозначный исторический no-answer Q10
отсутствует и не заменён другим вопросом. Полнота конечного ответа модели,
работа настоящего клиента OpenCode, общий recall, стоимость диалога и
полный CI не проверялись.

**Review поддерживает публикацию как воспроизводимого отрицательного
результата с уточнённым диагнозом delivery profile.** Production defaults,
source admission и бюджет сохраняются; готового общего исправления PR
не утверждает.
