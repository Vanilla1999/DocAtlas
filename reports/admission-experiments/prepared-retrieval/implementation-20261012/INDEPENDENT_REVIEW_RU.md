# Независимое review prepared retrieval до модели

Дата: 2026-10-12. Reviewer: F, независимо от авторов реализации и интеграционных
сценариев. Ветка `fix/main-flow-compact-evidence`, база
`8ad44222d19d2e8b886349aa3f0f13f71e9167ba`.

## Итог после адресного Run 05

**Открытых блокирующих замечаний в проверенном объёме не осталось.** Ошибка
attribution из Run 03 исправлена и независимо перепроверена по исходному коду
и четырём сохранённым конечным DTO Run 05. Bounded checklist сохраняет все
16 пунктов, занимает **758 / 900**, имеет `covered_query_ids=[]`,
`query_coverage=partial`, unverified качество и false answer/edit flags.

Это заключение опирается на полный Run 03, две заранее заявленные default
регрессии Run 04 и адресную перепроверку изменённого пути в Run 05. Полный набор
после последнего исправления повторно не запускался; дополнительные основания
для runtime reviewer не обнаружил. Исторические результаты не переименованы.

## Исторический verdict для Run 03

**Pytest: 4 PASS. Независимое продуктовое review: FAIL — обнаружено повышение
retrieval attribution при budget pruning.** Это разные результаты. Зелёные
assertions подтверждают перечисленные ниже свойства, но не закрывают найденный
дефект. Root принял замечание; его исправление и адресная повторная проверка
учтены отдельно ниже, с сохранением исходных Run 03 артефактов.

Reviewer не запускал продукт, pytest, collection, compile, модель или CI. Выполнены
статическое чтение реализации и тестов, чтение сохранённых JSON/XML и независимый
разбор конечных JSON относительно исходных файлов fixture. Изменён только этот
отчёт. Срез реализации Run 03 зафиксирован в [run-03-manifest.json](run-03-manifest.json).

## Найденный дефект после зелёного запуска

Для неизменного вопроса о dispatch checklist:

| Режим | Source rows | UTF8-quarter всего JSON | Covered IDs | Query/retrieval coverage |
|---|---:|---:|---|---|
| Default до опыта | 1 | 776 | пусто | partial |
| Broad, cap 12000 | 2 | 906 | пусто | partial |
| Broad, cap 900 | 1 | 757 | query-original | full |
| Default после опыта | 1 | 776 | пусто | partial |

В [wide packet](run-03-packets/context-3fc64e8f9b0a46498f92b6a59b3077ea.json)
первая строка источника **полностью совпадает** с единственной строкой
[bounded packet](run-03-packets/context-897755bc43344c85b5a5f4fc87fc7efb.json):
тот же snippet, span, hash, evidence ID и source URI. Удаление второй строки
не даёт основания повышать attribution.

Причина находится в `experimental_context_finalization._rebuild`: исходная
версия брала `retrieval_query_matches` и `_assigned_requirement_ids` из
`snapshot.source` и повторно строила публичную атрибуцию. Существующие structural
finalizers сохраняли более осторожный публичный результат. Поэтому скрытые
traces снова становились публичным credit при terminal repack.

Узкое исправление, согласованное с root: повторно проверить точный видимый
фрагмент существующим canonical qualifier и authoritative query plan; допустить
только свежие qualified, не admission-only traces в пределах **уже публичных**
covered IDs входного DTO. Assignment IDs без повторно проверенного visible
witness не переносить. Нельзя подменять это снятием cap, изменением вопроса,
новым scorer или обнулением действующих qualified маршрутов вне terminal repack.

Checklist-тест в Run 03 проверял факты, cap и false answer/edit, но не монотонность
attribution. Существующий сценарий усилен без новых продуктовых вызовов и без
изменения исходного корпуса, вопроса, 16 фактов или caps.

## Закрытие attribution defect: Run 05

В актуальном `_rebuild` точный публичный row передаётся существующему
`_requalify_visible_source` с текущим independent authoritative plan. В attribution
остаются только свежие `qualified=True`, не `admission_only`, query IDs из
публичного covered ceiling входного DTO. Assignment IDs явно пусты. Полный
исходный candidate не переносится в публичный row; передаются только row,
отфильтрованные matches/IDs и пустой список assignments. Таким образом старые
assignment fields не могут восстановить facet proof через `_payload`.

Изменённый файл и усиленный тест совпадают с [run-05-manifest.json](run-05-manifest.json).
[run-05.xml](run-05.xml) фиксирует 1 PASS за 1.854 s: 1 prepare, 4 context calls,
0 source-resource reads. Новая проверка монотонности attribution добавлена в
существующий checklist-сценарий, вместе с запретом повысить unverified качество
или facet coverage. Изменение критериев явно сохраняется в истории, а не
скрывается за неизменностью исходных фактов.

Reviewer независимо проверил все четыре Run 05 DTO:

- размеры полного JSON — **776 / 906 / 758 / 776** для default/wide/bounded/default;
- во всех четырёх присутствуют все 16 исходных пунктов и точные raw spans;
- [bounded packet](run-05-packets/context-078678e3eecd490cb74503ef169f842e.json)
  сохраняет ту же первую source row, что wide, но больше не повышает attribution:
  covered IDs пусты, query/retrieval coverage partial;
- default before/after совпадает целиком с прежними двумя исключениями parity;
- все answer/edit flags false, bounded status truncated, причина budget_limited;
- SHA256 фактического `docs/dispatch.md` одинаков в Run 03 и Run 05:
  `fb159801bc3fdcbfa0fd87014dc088572270683d84c133f721b8627df9908633`.

**Disposition: attribution blocker resolved.** Оставшихся выявленных source,
request, budget или default-compatibility blockers нет.

Отдельно [run-04.xml](run-04.xml) подтверждает 2 PASS за 0.811 s для заранее
объявленных публичных default-регрессий: неизвестный locator даёт отказ,
контекст остаётся доступным при недоказанном authority facet, без разрешения
ответа. Это два context calls; их существующая подготовка fixture идёт через
подтверждённый member service, а не через public prepare_docs MCP. Сами raw DTO
этих двух вызовов отдельно не сохранены и reviewer их не воспроизводил.

## Что действительно подтверждено Run 03

[run-03.xml](run-03.xml) содержит четыре завершённых сценария, без failures/errors/
skips, общее время 4.007 s. По фактическому коду сценариев и сохранённым результатам:

| Сценарий | Prepare/sync | Сохранённых context DTO | Выполненных resource reads |
|---|---:|---:|---:|
| Составной вопрос optics | 1 | 2 | 2 |
| Prepared/default parity и scope | 1 | 10 | 1 |
| Legacy, stale, sync и restart | 2 | 6 | 3 |
| Checklist и terminal cap | 1 | 4 | 0 |
| **Итого Run 03** | **5** | **22** | **6** |

Число context DTO независимо пересчитано в `run-03-packets`; resource counts
сверены с XML properties и точками вызовов в сценариях. Это 4 интеграционных
сценария, а не 22 независимых задания качества. Ответы source resource отдельно
не сохранены; их status/hash/span проверены assertions теста, а не повторным
чтением ресурсов reviewer.

### Факты, исходный текст и порядок

- В optics baseline (365) имеется только `docs/issue.md`: оба факта о получателе
  и подписи присутствуют, оба факта об упаковке отсутствуют. Broad packet (816)
  содержит оба документа и все четыре независимых факта. Старое значение
  `query_coverage=full` у baseline не используется как доказательство полноты.
- Во всех четырёх checklist-пакетах присутствуют все **16** исходных пунктов.
  При cap 900 удалён отдельный раздел Filing after arrival, а checklist целиком
  сохранён. У bounded packet явно `status=truncated`, качество `unverified`,
  причина `budget_limited`; answer/edit остаются false.
- Независимо сверены **34 source rows** во всех 22 DTO с реальными исходными
  файлами fixture и соответствующей редакцией issue.md. Все snippets находятся
  в объявленных исходных line spans с сохранением LF. Нет обратного порядка,
  повторов или перекрытий диапазонов внутри одного документа. Разные документы
  могут чередоваться в выдаче; это не нарушение их локального порядка.
- Все видимые rows имеют ожидаемые project/module scope, `source_of_truth`,
  `unversioned`, непротиворечивую project identity и 64-символьный projection
  fingerprint. Fingerprint публичной row не объявляется raw SHA файла.
- Ни один сохранённый DTO не устанавливает `answer_supported`,
  `answer_available` или `edit_ready` в true.

### Полный JSON и cap

Reviewer независимо пересериализовал каждый публичный DTO с обычными JSON
разделителями и без ASCII escaping и пересчитал `ceil(UTF8_bytes/4)`; все **22**
значения совпали с сохранёнными proxy. Размеры ключевых экспериментальных
пакетов: optics 816 при cap 12000; checklist 906 при cap 12000 и 757 при cap 900;
stale refusal 155 при cap 900. Это стоимость всего публичного DTO, включая
декорацию и URI. Это не размер полного prompt клиента/host и не модельный usage.

Продукт дополнительно считает встроенный offline o200k_base на том же JSON;
reviewer его повторно не вызывал. Нынешний stale packet сам по себе мал, поэтому
он подтверждает конечный cap и сохранение отказа, но не проверяет удаление
чрезмерно большой recovery-инструкции.

### Parity, scope и lifecycle

Независимое сравнение **всех полей DTO**, с единственными заранее объявленными
исключениями `sources/read_next.source_uri` и верхнего `estimated_tokens`,
подтвердило:

- два shutter positive DTO при prepared off/on совпадают;
- все три exact negative DTO пусты и совпадают; XML отдельно фиксирует PASS
  действующего empty-source контракта, source count 0;
- два legacy DTO (обычный parser и prepared flag без manifest) совпадают;
- три DTO обновлённой редакции (parser, prepared reader, restart) совпадают;
- default checklist до и после опыта совпадает, включая порядок sources.

Module/all запросы доставляют `modules/imaging/guide.md` с module scope;
project-only запрос этого материала пуст. Unlisted document и другой проект
не доставляют источники.

После изменения issue.md [stale packet](run-03-packets/context-e19bf6322a3849ecba140949aa0285f4.json)
не содержит источников, имеет `context_available=false`,
`requires_confirmation=true`, `delivery_decision.deliverable=false` и причину
preflight confirmation. Тест проверяет отказ старого continuation без snippet.
Только явный sync публикует новое поколение; после него доставляется
instrumentation registrar, старый collection custodian отсутствует, restart
сохраняет результат. Assertions сравнивают файлы и логическое содержимое SQLite
до/после чтений: скрытого sync или записи при query эти сценарии не обнаружили.

## Статическое review и история исправлений

До анализа Run 03 reviewed A/B не имели открытых блокирующих замечаний:
сохранялись source/request/member/generation/hash/span/owner/lifecycle guards,
live request receipt и существующие qualified/literal маршруты. Prepared
manifest сверяется с canonical parser, reader не сертифицирует произвольные
плохие rows, legacy generation сохраняет parser fallback, query ничего не
перестраивает. Canonical parser/config/chunk identity не менялись.

В C reviewer обнаружил и перепроверил два исправления lineage:

1. Для core crop сохранялся широкий native reference envelope; выбор relation
   по нему ошибочно классифицировал фактически меньший snippet. Теперь
   structural relation определяется по проверенному видимому occurrence.
2. Первый вариант исправления наследовал лимит 262144 символа helper-а structural
   expansion. Native crop теперь проходит прямой `contained_span` recheck без
   такого ограничения. A независимо проверяет source, live seed и relation.

Финальный source/request recheck выполняется после structural finalizers;
полный cap — после recovery decoration и повторно после регистрации ресурсов.
Trace additions копируют уже измеренные счётчики и timings, не вызывая новые
retrieval или модель. Первоначальный статический verdict C был без открытых
blockers; последующее чтение реальных packets выявило описанный выше пропуск
в attribution, поэтому статический verdict не выдаётся за доказательство
полной корректности.

История verifier сохранена в [execution_ledger.json](execution_ledger.json) и
[CONTRACT_DECISION_RU.md](CONTRACT_DECISION_RU.md):

- до runtime whitelist parity comparator заменён сравнением полного DTO с
  двумя явно названными исключениями;
- Run 01 остановился до подготовки/запроса: fixture жёстко требовал отсутствующий
  `/tmp`; стандартный TemporaryDirectory устранил setup defect, настоящая
  storage policy осталась;
- Run 02 выполнил 1 prepare и 1 default context, затем verifier ошибочно удалил
  завершающий LF через splitlines/join; keepends исправил реконструкцию;
- до первого broad output исправлена неверная предпосылка empty covered IDs:
  сохранён existing retrieval-only credit и введена проверка отсутствия новых
  IDs относительно baseline. Это **изменение assertion/предпосылки verifier**,
  а не доказательство неизменности самого тестового файла;
- документы, обе редакции, вопросы, обязательные факты и caps не менялись ради
  PASS. Run 03 — первый завершённый broad run, а его attribution defect найден
  после pytest PASS; исправление и адресный Run 05 описаны отдельно выше.

## Границы результата

Проверки проходят через публичный in-process MCP с настоящими подготовкой,
SQLite retrieval, selection, validation и source resources. Проверяемые этапы
не подменены mocks. Это не installed-stdio, реальный внешний клиент или production
smoke. Новых заданий генерации ответа и forward-вызовов моделей здесь нет.

Reader parity и наличие manifest не являются сами по себе runtime-доказательством
числа prepared hits, отсутствия parser calls или ускорения. В публичных packets
таких counters нет. Тестовое время 4.007 s не сравнивает latency on/off. Семантическая
релевантность arbitrary broad кандидата, достаточность корпуса/набора и качество
ответа модели остаются за пределами доказательства. Совпадение aggregate
covered IDs не устанавливает, какой source дал credit; поэтому независимый
разбор конечных метаданных остаётся существенной частью review.
