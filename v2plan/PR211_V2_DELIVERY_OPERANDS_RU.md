# PR211: наблюдение причин отказа выдачи V2

Статус: узкая диагностика подготовлена; новый runtime ещё не выполнялся.
Никакой новый PASS или доказательство исправления V2 этим документом не заявляется.

## Сохранённый фактический результат

На опубликованном HEAD `eb2c4f3b3e0065110a1bfe2c855e4a05803fa37a`
(tree `6d75a3b5f019e94c11810364a7214b442b5829fa`) случай
`v2-natural-request-flow` задавал исходный вопрос:

> Как проходит запрос get_docs_context от MCP-входа до выбора источников?

Сохранённый receipt:
[`RUNTIME_EVIDENCE_eb2c4f3b.json`](pr211-execution/RUNTIME_EVIDENCE_eb2c4f3b.json),
blob `9fe0b0303037ca91077775faf77eeba9e6dee2bd`,
поле `advanced.v2_focused`. У исходного вопроса были три уже заданных
host lookup. В сохранённом preview есть qualified окна для `query-lookup-2`,
но итоговая выдача содержит 0 sources и
`delivery_decision={deliverable:false,reason_code:"required_evidence_missing"}`.
Существующие observer counts: retrieval 1, validation 1. Projection,
ranking и coverage отмечены `not_reached` в public projector trace;
это не означает, что более ранний ProjectContext reranker не вызывался.

## Что установлено исходниками и чего пока не хватает

MCP `context_tools.get_docs_context` возвращает явный blocked packet через
`_explicit_delivery_block` до вызова `project_docs_context`.
В Unified `read_context_eligible` отдельно зависит от наличия контекста,
project delivery, статусов и подтверждений lanes и актуальности библиотек.
При отказе итоговый reason берётся из существующего support payload.
Поэтому `required_evidence_missing` сам по себе не доказывает, что причиной
отказа чтения была именно неполнота ответа.

ProjectContext, в свою очередь, проверяет наличие context pack, текущий
catalog, consent, stale/status и реальные результаты ограничений обработки.
Сохранённый receipt не содержит всех промежуточных возвращённых DTO;
по нему нельзя выбрать один из этих операндов как фактическую причину.
Accepted ADR0003 разрешает полезный частичный контекст без answer/coverage
credit, но сохраняет source, scope, lifecycle и consent veto.

## Узкое изменение наблюдения

Существующий self-host evaluator наблюдает три уже выполняемых возврата:
member `get_project_docs`, project `get_project_context` и Unified
`get_docs_context`. Обёртки вызывают исходный bound method один раз,
передают исходные arguments и возвращают исходный объект без изменения.
Используется тот же materialized read facade; новое создание service,
retrieval, coverage, filesystem и network calls не добавлены.

Сохраняются только выбранные фактические поля:

- statuses, delivery, confirmation, support IDs и requirements;
- исходный запрос и producer `request_scope`;
- количество окон, source/chunk IDs, stable IDs, paths, raw offsets, hashes и qualified query IDs;
- выбранные routing stage counts/bytes/status и trust reason.

Для identity/span whitelist используется фактическое верхнее поле DTO,
а при его отсутствии — одноимённое metadata поле. Явный верхний `None`
сохраняется. Это позволяет сопоставить также carrier `RetrievedChunk`,
у которого identity находится в metadata; `text` не читается.

Source content, snippets, raw documents, source-reference bodies, действия
и произвольные diagnostics целиком не копируются. Отсутствующий список или
trace остаётся unknown; `None` и явный `False` не отождествляются.
Каждый preview списка имеет полный `count` и `omitted`; лимит 32 относится
только к служебному выводу. Отсутствие ID в preview не доказывает его отсутствие
в полной выдаче. Счётчик `return_counts` считает наблюдённые успешные возвраты,
а не приписывает завершение вызову, который выбросил исключение.
Ошибка самой сводки сообщает только тип ошибки и не меняет исходный result.

V2 printer добавляет одно поле `delivery_observations` к прежнему whitelist
и применяет прежний bounded formatter. Public DTO и assessment его стоимости,
корпус, вопросы, scorer, thresholds, guards и CI verdict не меняются.
Служебный JSON/log расширяется. Существующие Legacy104 capture и
`observer_counts`, включая реальную семантику retrieval/validation 1/1,
остаются прежними. Существующие локальные coverage calls не добавлены и
не удалены.

## Manifest и статическая проверка

| Файл | Base blob | Proposed blob | Mode |
| --- | --- | --- | --- |
| `scripts/run_project_docs_self_host_gate.py` | `3e044b27c4d1809c869329e4241ac68e3c28b70c` | `3d04068a9bb4a7d2c34148db74194c3d4b4ffb53` | `100644` |
| `scripts/run_project_context_quality_v2_gate.py` | `82cd79d19d22b37859e72afafea157c995cc200b` | `fce272e8ee24fcb199c91a27d773d7b1dbb3d380` | `100755` |

Для runner проверены 6 точных замен и побайтное восстановление base обратным
diff; для printer — одна whitelist замена. Оба GitHub blob прочитаны обратно
и совпадают с подготовленным текстом. Локальные Python/import/AST/pytest
не запускались. Независимый source review запрошен перед публикацией.

Следующий обычный PR CI должен показать первый наблюдаемый переход, где
полезные окна исчезают либо остаются при delivery veto. Затем нужен узкий
разбор именно фактического операнда и независимый finite fixture;
автоматическое разрешение выдачи или ослабление qualification не предлагается.
