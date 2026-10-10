# PR211: V2 — квалификация и сохранность найденных окон на SHA 441cdefd

## Вывод и предел доказательства

В двух доступных случаях **все окна с непустыми `qualified_query_ids` на
наблюдённом member-return дошли до project context, Unified и public sources**.
Числа 20→3 и 20→1 не доказывают потерю уже квалифицированного контекста.

Недостающие frozen facts существуют в текущих документах и были возвращены
member reader. Их конкретные окна не прошли квалификацию. Это остаётся
реальной quality-проблемой; запись не меняет gold, lookup text, thresholds,
admission, retention или verdict. Она не предлагает сохранять все 20 candidates.

Доказательство ограничено двумя полными member-return списками. Более ранний
qualification preview ограничен 32 строками; сохранность всех кандидатов до
этого return не утверждается. Retention sinks и ACK в этих observations не
записаны, поэтому их состояние не выводится из сигнатур функций.
`v2-natural-request-flow` отсутствует в доступном console receipt: его
delivery operands здесь **неизвестны**.

## Actual источник

- PR HEAD: `441cdefd2b251d63f716bfa75b053413bbe09c76`.
- Merge checkout: `ceea2571e9847a71515feda4e1e1441fafdede44`.
- Tree: `f0ad2af2fed811e884cc3d9887d7fb9ecd2812df`.
- [Acceptance reader](https://github.com/Vanilla1999/DocAtlas/actions/runs/38017123447/job/114111640263).
- [Сохранённый receipt](RUNTIME_EVIDENCE_441cdefd.json),
  blob `ea7d1171ab2c3c1d72936e92302eafb72c1f8ead`,
  SHA-256 `eff1c75f1dc6e4b84069b16e29595ab4413ebc07ded1e7af09238797a687782a`.
- Два `V2_FOCUSED_STAGE` records относятся к уже выполненному
  `project-context-quality-v2-live.json`, SHA-256
  `2976af5e9a3cf3b18001dc3a3177b297a65fae33de47b20058b9afc7458f4330`.
  Нового product runtime для этого аудита не выполнялось.

В каждом record наблюдены ровно по одному member, project-context и Unified
return. Все списки ниже полны для этой границы: 20 member windows и 3/1 context
windows, без omitted rows. Индексы таблиц — **с нуля**, spans — полуинтервалы
Unicode characters исходного документа.

## 1. Очистка индекса: оба gold witnesses в неквалифицированном окне

`v2-paraphrase-cache-reset`.

Original: `I want a dry look at what an index reset would remove, with my source tree and configuration left alone. What is the documented process?`

| Lookup | Точный исходный текст |
| --- | --- |
| query-lookup-1 | Can index removal be previewed without applying it? |
| query-lookup-2 | Does clearing derived storage preserve source files and configuration? |

Нужный member index **6**, `docs/index-cleanup.md` **[0:282]**:
`child-b2f5340361bc8ba63cac08b1c9c063a67e5896b9`.
Current, active, stale=false, scope=project, module_path=null;
`qualified_query_ids=[]`. Raw window SHA-256:
`280cdd40ddb5763594677743138fa2cf27ff1351d901908d6b4663be45840053`.

Он содержит оба сохранённых witnesses: `preview-only` и
``preserving project\nsources, `docatlas.yaml`, configuration, and unrelated files``
(перенос после `project` показан как `\n`; здесь нет переписывания source bytes).

| Query | Наблюдённые body matches | Ratio | Verdict |
| --- | --- | ---: | --- |
| lookup-1 | index, it | 2/8 = 0.25 | insufficient_visible_match |
| lookup-2 | derived, files, and, configuration | 4/9 = 0.4444 | insufficient_visible_match |
| original | index, and, configuration, is, the | 5/24 = 0.2083 | insufficient_visible_match |

Qualifier `reference_visible_span=[0,280]` сохраняет оба факта; два последних
символа raw window — завершающий whitespace. Потери самого witness при
подготовке visible span здесь не обнаружено.

Соседний member index **1**, cleanup **[282:868]**, квалифицирован по lookup-1
через `can,index,be,it` (4/8). Он содержит другую формулировку
`preserves project sources`, но не `preview-only` и не exact frozen
`preserving project sources…`. Этот paragraph действительно доставлен целиком.
Поэтому lookup coverage **1/2** совместимо с frozen fullfact coverage **0/2**.
Это не даёт основания менять gold на фактически пришедший текст.

### Полная сохранность трёх квалифицированных окон

У всех ниже только `query-lookup-1`; stable ID и raw span совпали в member,
project context и Unified. SHA-256 публичного snippet совпал с
`raw_window.strip()` из того же текущего документа.

| Member index | Stable ID | Path и raw span | Public snippet SHA-256 |
| ---: | --- | --- | --- |
| 0 | child-4828fda17c7f3b531b37a3343153f23b122558e9 | README.md [15446:15953] | 2d4edb0bd6335820946c000ab9c2c09580e8575eb7e9e71e63a28975561af1c8 |
| 1 | child-27f6f9ed9c0008e4844633ff07e492722480784e | docs/index-cleanup.md [282:868] | 0944ba4216885d2e1d8cff4db2f9f883264a92434cdf9541c5b75eb18d54509c |
| 2 | child-19b428c2cd63f3958b0dbc1094ce3b6dd18f302d | docs/index-cleanup.md [3146:4214] | 8903e836f9e3c3c528a98b0b73633ca99b8d467ad5839ccc4eec77a4b94a90bf |

Остальные 17 member windows имеют пустой qualified-query список.
Public status=ok, support_status=retrieval_only, sources=3;
answer_available/answer_supported/edit_ready=false.

## 2. Архитектура: три факта дошли, infrastructure witness не квалифицирован

`v2-natural-architecture`.

Original: `Как устроена архитектура проекта и где проходят основные границы модулей?`

| Lookup | Точный исходный текст |
| --- | --- |
| query-lookup-1 | How are application workflows separated from domain rules? |
| query-lookup-2 | Where does the documentation transport boundary live? |
| query-lookup-3 | Which responsibilities belong to storage rather than evidence qualification? |

Member index **0**, `docs/PROJECT_MAP.md` **[198:1356]**,
`child-8072f565a53c7532e3032559eac6b38aa0adc79c`,
квалифицирован по lookup-1 (`application,workflows,domain,rules`, 4/8).
Тот же ID/span проходит project context и Unified; public snippet SHA-256
`9a95644156fa7db60960cc57fc841b4b47154bf9a5904003162340b520599f90`
равен stripped текущему raw window. Других qualified member windows нет.

Это окно содержит application, domain и MCP boundary — actual fullfacts **3/4**.
При этом его lookup-2 отклонён: `documentation,transport,boundary` = 3/7,
0.4286. Lookup coverage **1/3** и факт MCP boundary=True отражают разные
проверки; lookup credit не повышается из факта или другого query.

Недостающий infrastructure witness находится в member index **3**,
`docs/modules/project-context-retrieval.md` **[2053:2526]**:
`child-3b189a9ab357a4f923ef08424372cd0564adf94c`.
Current, active, stale=false, scope=module, module_path=`docmancer/docs`;
`qualified_query_ids=[]`. Raw SHA-256:
`dab07db4b53375f545671704afb37e224e5feb6ccbf419120933dc079e274faf`.

Текущий paragraph содержит:
`SQLite owns persistence and candidate generation; metadata-only matching may discover a candidate but cannot qualify public evidence`
с исходными переносами строк после `and` и `but`.
Qualifier visible span **[2053:2524]** содержит весь witness.

| Query | Наблюдённые body matches | Ratio | Verdict |
| --- | --- | ---: | --- |
| lookup-1 | application, domain | 2/8 = 0.25 | insufficient_visible_match |
| lookup-2 | the | 1/7 = 0.1429 | insufficient_visible_match |
| lookup-3 | evidence, qualification | 2/9 = 0.2222 | insufficient_visible_match |
| original | пусто | 0/10 | insufficient_visible_match |

Остальные 19 member windows имеют пустой qualified-query список. Public sources=1, status=ok,
support_status=retrieval_only; answer_available/answer_supported/edit_ready=false.

## Проверка текущих source bytes и границы выводов

Документы прочитаны по exact113 HEAD. SHA-256 полных файлов независимо
пересчитаны и совпали с actual `candidate.source.content_sha256`:

| Path | Git blob | Full source SHA-256 |
| --- | --- | --- |
| docs/index-cleanup.md | 7d833b5706fd72e7355f45959a1348ebd6f60754 | aa0a4e6202a92b7e7d28c6d896f53cec6933297aee91fdb430fabb1c132d9420 |
| README.md | 87538663c6a08a5a4e087137880613bd0e946c4e | bf435264f9e773070666011e12509a6948476098f1dcdab3407ce9cd0e5014a7 |
| docs/PROJECT_MAP.md | 634750dd90e86fb168ce50e8f00b1dee44841492 | 2345cbcb88feba7b44b257785e79cff9466d62edb45875ad1a9d3afde2967a22 |
| docs/modules/project-context-retrieval.md | bcb180b3042361e68f07764f5f93fcee1681b74c | 6e4d1c68ffd94154f03d1d346de9a2bb144511502e3ca22f43f203dbada864bc |

Frozen cases/obligations:
`eval/project_context_quality_v2/cases.json`,
blob `ca1104d65ebe35a91a84a2a2361b7675c8780c46`.

Оба actual project/Unified return имеют status=success,
requires_confirmation=false и явный delivery_decision.deliverable=true;
routing budget не превышен. Outer `required_evidence_missing` у Unified
в этих двух случаях — состояние answer support, не delivery veto.

Source объясняет допустимую границу фильтра:
`_project_context_service_part01.py`
(`4bbc35fe1ccb6c947a74b1eb58662521a9d51554`, 156–165)
вызывает `rerank_project_doc_chunks`;
`project_doc_ranking.py`
(`b2cfa8385c2381cd93fc507a35e61b1cc1e33ca9`, 217–225)
не разрешает rank исправлять failed qualification без отдельно проверенного
literal/context-candidate основания. Это source-derived объяснение;
receipt не записывает каждый внутренний выбор конкретной ветви.

Следующая проверка — отдельные actual delivery operands request-flow на новом
SHA. Для изменения relevance/admission понадобится самостоятельный контракт с
independent positive/negative controls, сохраняющий source identity, full fact
и отсутствие original/answer/edit credit. Этот audit не является таким fix.
