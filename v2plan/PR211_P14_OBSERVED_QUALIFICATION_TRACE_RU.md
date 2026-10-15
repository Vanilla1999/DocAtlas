# P1.4: наблюдаемые входы qualification, без повторных запросов

## Цель slice

На `067dd56044fb1fe292af2d17783154c8a4b7c092` P1.4 закончил выполнение: 7/14 cases, discovery 3/10, complete fact 2/5, errors 0. Семь quality failures сохранили `state_equal=true` и пустые differences; остальные семь прошли все checks. Это подтверждает исправление read-only границы, но не полноту retrieval.

Источник фактического результата: [job 114025928063](https://github.com/Vanilla1999/DocAtlas/actions/runs/37991321105/job/114025928063). Первый незакрытый положительный случай — исходный `What does OrdersDraftStore do?` и неизменённый authored body в `packages/orders/README.md`.

Одна гипотеза из source review: canonical reference qualification учитывает все четыре literal terms, body содержит один, точного explicit symbol constraint для bare CamelCase нет. Нужны фактические сохранённые stage values; этот slice не объявляет гипотезу доказанной.

## Что добавлено

Только private `_project_docs_diagnostics.py`, уже вызываемый после retrieval/tagging и перед selection, получает дополнительные поля в существующих `qualification_outcomes`:

- SHA-256 и character count уже полученного body window.
- Наблюдаемый source identity, scope/generation, finite member binding и span; raw document/body не копируются.
- Существующие root reference roles, states, explicit flags, точные mention spans, состояние полноты каталога. Сохраняется число references, выводится не более прежних 32 диагностических записей.
- Существующие canonical query text/body query, terms, exact terms, body/visible matches, ratio, missing constraints, qualification route и query-local lexical score.
- Существующая запись literal-context admission либо `null`, если записи нет.
- Уже вычисленная `candidate_lexical_match`: mode, terms, field matches, BM25 cost и score.

Последний блок принадлежит acquired candidate. После объединения нескольких retrieval lanes он не является отдельной original-query BM25 receipt. Поэтому он явно назван candidate-level; query-local route/score и admission flags выведены отдельно. Никакой новой attribution эта диагностика не создаёт.

## Границы

Helper только копирует выбранные поля и вычисляет hash уже имеющейся строки. Он не вызывает engine, store, reference resolver, qualifier или admission routine. Нет дополнительных SQL/disk/network reads, новых queries, переписывания вопроса, aliases или inference ролей.

Qualification outcomes, reason, ids и прежние limits diagnostic observer сохраняются. Public payload, scorer, frozen questions/facts/negatives, candidate selection и projection не меняются. Новый semantic fallback здесь не добавляется.

P1.4 runtime уже сохраняет `qualification_outcomes` полностью. Ранее reviewed reporting slice `c7ca00ed831d40a041d0580ace3da94d0967a808` выведет эти дополнительные поля в обычном CI; ещё один вызов derive или отдельная runtime правка не требуются.

## Manifest и проверка

Base commit: `067dd56044fb1fe292af2d17783154c8a4b7c092`.

| Путь | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| `docmancer/docs/application/_project_docs_diagnostics.py` | `bd4beaca068f84ca94e0b8290774fe2ca6c509ba` | `f222ebfcedea00acf5cf04a76ee8d9be32009f9e` | 100644 |

По exact source проверены producer поля `reference_query_tagging`, `prepare_reference_probe`, `qualify_evidence`, `SourceReferenceContext.prepare`, SQLite lexical trace и сохранение runtime diagnostics. Python imports/compile/pytest и local subprocess не запускались. Следующий обычный P1.4 job должен показать фактические значения на опубликованном SHA; до этого runtime validation pending.
