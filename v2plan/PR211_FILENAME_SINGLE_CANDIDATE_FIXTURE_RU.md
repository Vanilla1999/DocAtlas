# PR #211: коллизия filename при одном реально полученном документе

## Фактический отказ на 113

PR HEAD: `441cdefd2b251d63f716bfa75b053413bbe09c76`.
Merge checkout: `ceea2571e9847a71515feda4e1e1441fafdede44`.

[Main CI](https://github.com/Vanilla1999/DocAtlas/actions/runs/38017123447)
и [acceptance reader](https://github.com/Vanilla1999/DocAtlas/actions/runs/38017123447/job/114111640263)
показали recovery baseline **11 PASS / 1 FAIL / 0 ERROR**.
Единственный отказ: `closed_literal_context`,
guard `recovery_filename_withheld_real_candidates`.

В этом прогоне public negative `unreturned_collision` уже прошёл свой
`recovery_filename_catalog_ambiguity`; после него упал отдельный fixture guard.
Старый guard требовал одновременно получить `manual/queue-window.md` и
`archive/queue-window.md` внутри dispatcher, убрать второй и оставить первый.
Detail этого guard не содержал capture и количества кандидатов. Поэтому actual
113 не устанавливает, какой путь пережил acquisition, сколько было вызовов и
был ли список пустым. Пустой `RECOVERY_FAILURE.capture` относится к отсутствию
detail у fixture assertion; он не доказывает отсутствие dispatcher calls.

Контрольные суммы прочитанного evidence:

| Объект | SHA-256 | UTF-8 bytes |
| --- | --- | ---: |
| Декодированный reader job log | ad44754505bf41a660a8312924380d8989915f6cf776a0579ae84f45edbf0f59 | 569005 |
| recovery baseline.json | 8e2fc4f88678d92f370e16e2c3cab25fd35b9eaa88e366e0cdf656640d8195d5 | 5963 |
| Исполненный structural_filename_controls.py | 383a41e093cba26c86564b83485f2ea3cc593395c4f85a4b1a26c90a011390c3 | 25499 |

Mutation gate отклонил красный baseline. Новый результат **12/33** здесь
не заявляется.

## Причина по действующему контракту

В `SQLiteStore.query`
(`docmancer/core/_sqlite_store_part03.py`,
blob `96f35c1f02a97f58f05b15f154c2fc45487487dc`, строки 227–256)
`seen_content` удаляет повторный `title + "\n" + text` независимо от пути
источника. У двух fixture members один basename и одинаковый полный body.
Таким образом, действующий acquisition вправе вернуть только один документ
из этой пары. Требование вернуть оба противоречит разрешённой дедупликации.
Это вывод по исходникам, а не новое наблюдение списков actual 113.

Полноту naming проверяет другой carrier:
`SourceReferenceContext` строит полный текущий naming inventory до фильтра
`project_doc_path`; обычный список acquisition sources остаётся ограниченным
явно выбранным путём. `member_document` записывает оба исходных поля
`project_doc_path` и `source_path`; fixture не выводит путь из текста.

Production дедупликация, ranking, source resolver, admission и projector
в этом срезе не меняются.

## Исправленная проверка

Обязательный прежний независимый probe остаётся перед native interception:
`SourceReferenceContext(..., project_doc_path=manual/queue-window.md)`
имеет **один выбранный source**, полный naming inventory из **двух** members,
и structural locator со state `ambiguous` и двумя точными source IDs.
Он не зависит от порядка retrieval, top-k или наличия public sources.

Native observer вызывает исходный dispatcher ровно один раз на каждое
перехваченное обращение. Из фактически возвращённых chunks он выбирает первый
реальный current-member path, затем сохраняет не более одного исходного chunk
этого пути на вызов. Выбор не требует заранее предпочесть `manual` перед
`archive`; вопрос и оба source bodies остаются прежними. Других retrieval
вызовов, повторных public requests или записи в storage нет.

Если native candidate получен, control обязательно проверяет:

- producer preparation действительно сохранила этот же единственный путь;
- каждый prepared record содержит полный текущий inventory из обоих members;
- raw document и source SHA-256 совпадают с текущими fixture bytes выбранного member;
- root plan остаётся `ambiguous` с теми же двумя IDs, что у независимого probe;
- public payload не содержит sources, context availability или answer/edit authority;
- storage и project fingerprints остаются прежними.

Если корректный public veto произошёл до acquisition или native candidates
не получены, этот control не требует дополнительного чтения. Независимый probe
с одним выбранным source и полным каталогом по-прежнему обязателен.
Поле `single_candidate_observed` при этом равно `false`: отсутствие native
наблюдения не выдаётся за доказанный single-candidate delivery.

В результат добавлен body-free `single_candidate_acquisition`: фактические
числа вызовов/chunks, возвращённые/оставленные пути, исходные fixture query,
полный roster и canonical ambiguous IDs. Два новых fixture assertions
передают этот detail и уже существующий capture для прежнего failure printer.
Числа отражают наблюдение; успешное прохождение ветки ещё требует CI.

## Сохранённые guards и состав

Не меняются 12 recovery case names, 33 directed mutation definitions и их
source anchors. Все восемь filename mutants достигают прежних intended guards
раньше исправленного блока: healthy source fact, первый catalog collision,
независимый global recheck, target-role forgery, complete syntax, whole label
и отдельный path-selection probe. Исправление не переносит их первый отказ.

Остаются прежние 33 public reads, 25 negative labels, шесть structural positives,
два legacy positives, 21 filename replay, 13 immutable replay controls,
17 finite preparations и один отдельный path-scope fingerprint check.
Это число предусмотренных операций fixture, а не утверждение об их полном
успешном выполнении на 113. Вопросы, bodies, gold/scorer и все production files
сохранены; новых обычных test functions нет.

## Review manifest

| Путь | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| eval/agent_developer_v1/structural_filename_controls.py | f31fb0fdc9e970a04fa14f9a97e3c22ea74c3c23 | beff197e7c8a4280cfc1ca59cfa5674fe963eb61 | 100644 |
| v2plan/PR211_FILENAME_SINGLE_CANDIDATE_FIXTURE_RU.md | новый файл | этот документ | 100644 |

Изменён только поздний interception/assertion block и одна строка результата.
Обратная замена восстанавливает base побайтно. Proposed helper:
SHA-256 `8007a304e779ca0166ad542dca2447d3fe6c6047425d798ae302918c88fcdd61`,
27724 UTF-8 bytes, 432 строки. GitHub blob roundtrip совпал.
Source review выполнен без local runtime, imports, pytest или новых dependencies.
Совместный recovery baseline и directed mutation proof на конечном SHA
остаются **PENDING** до обычного CI.
